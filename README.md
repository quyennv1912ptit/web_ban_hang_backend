# Web Bán Hàng Backend

## Giới thiệu

Backend cho ứng dụng thương mại điện tử một nhà bán hàng, xây dựng bằng FastAPI. Dự án cung cấp API cho danh mục và sản phẩm, tài khoản người dùng, giỏ hàng, yêu thích, địa chỉ giao hàng, đơn hàng, đánh giá và các thao tác quản trị. Đăng nhập được xác thực bằng Firebase; dữ liệu lưu trên PostgreSQL. Tìm kiếm sản phẩm hỗ trợ lọc thông thường, tìm kiếm ngữ nghĩa bằng văn bản và tìm kiếm bằng ảnh.

Thanh toán VNPay/Momo và webhook chưa được tích hợp. Endpoint thanh toán trực tuyến hiện chỉ mô phỏng luồng thanh toán.

## Công nghệ

- Python 3.14 trở lên, FastAPI, SQLModel và Pydantic Settings.
- PostgreSQL với extension `pgvector` (phiên bản hỗ trợ HNSW, từ 0.5 trở lên) để lưu và truy vấn embedding.
- Firebase Admin SDK để xác thực token và đồng bộ thông tin người dùng.
- Cloudinary để lưu ảnh sản phẩm.
- BGE-M3 và JinaCLIP v2 cho tìm kiếm văn bản và ảnh; lần chạy đầu tải model từ Hugging Face.
- `uv` để quản lý môi trường và cài đặt dependency theo `uv.lock`.

## Cấu trúc thư mục

```text
.
├── src/web_ban_hang_backend/
│   ├── api/routers/  # Các nhóm endpoint FastAPI
│   ├── core/         # Kết nối database, Firebase, auth và dependency
│   ├── models/       # Model SQLModel ánh xạ bảng PostgreSQL
│   ├── schemas/      # Schema request/response
│   ├── services/     # Tìm kiếm, embedding và xử lý ảnh
│   ├── config.py     # Đọc cấu hình từ .env
│   └── main.py       # Khởi tạo FastAPI, middleware và router
├── db.sql            # Cấu trúc bảng và index PostgreSQL
├── pyproject.toml    # Python version và dependency
└── uv.lock           # Phiên bản dependency đã khóa
```

## Cài đặt và chạy

Clone repository về máy, sau đó mở PowerShell tại thư mục gốc (thư mục có `pyproject.toml`). Các lệnh bên dưới giả định đang chạy từ thư mục này.

### 1. Chuẩn bị

Cài Python 3.14 trở lên, PostgreSQL có hỗ trợ `pgvector`, và [uv](https://docs.astral.sh/uv/). Có thể để uv cài Python 3.14 nếu máy chưa có:

```powershell
uv python install 3.14
```

Tạo một database PostgreSQL mới, ví dụ `web_ban_hang`:

```powershell
createdb -h localhost -U postgres web_ban_hang
```

Máy chủ PostgreSQL phải cài extension `pgvector`; chỉ chạy `CREATE EXTENSION` là chưa đủ nếu gói extension chưa được cài trên máy chủ. Có thể dùng pgAdmin để tạo database nếu chưa có `createdb` trong `PATH`.

### 2. Tạo schema database

Kết nối tới database vừa tạo và bật `pgvector`:

```powershell
psql -h localhost -U postgres -d web_ban_hang -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

File `db.sql` là schema snapshot. Để nhập sạch trên database mới, bỏ câu tạo schema `public` (PostgreSQL đã tạo schema này) và các dòng `CREATE UNIQUE INDEX` (các index duy nhất đó đã được tạo bởi ràng buộc `PRIMARY KEY`/`UNIQUE` trong phần tạo bảng). Trong PowerShell, tạo bản tạm đã lọc rồi nhập:

```powershell
Get-Content .\db.sql |
  Where-Object { $_ -notmatch '^CREATE SCHEMA "public";$' -and $_ -notmatch '^CREATE UNIQUE INDEX ' } |
  Set-Content .\db.local.sql -Encoding utf8

psql -h localhost -U postgres -d web_ban_hang -v ON_ERROR_STOP=1 -f .\db.local.sql
Remove-Item .\db.local.sql
```

Lệnh `psql` sẽ hỏi mật khẩu PostgreSQL. Nếu dùng tài khoản, máy chủ hoặc cổng khác, thay `postgres` và `localhost` cho phù hợp. Chỉ nhập schema một lần trên database rỗng. Có thể xác nhận các bảng đã được tạo bằng `psql -h localhost -U postgres -d web_ban_hang -c "\dt"`.

### 3. Cấu hình biến môi trường và dịch vụ

Tạo file `.env` ở thư mục gốc của repository. Ví dụ:

```dotenv
DB_URL=postgresql+psycopg2://postgres:your_password@localhost:5432/web_ban_hang
FIREBASE_CREDENTIALS_PATH=./serviceAccount.json
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

- `DB_URL`: chuỗi kết nối tới database ở bước trên. Mã hóa các ký tự đặc biệt trong mật khẩu theo định dạng URL.
- `FIREBASE_CREDENTIALS_PATH`: đường dẫn tới khóa service account JSON của Firebase Admin SDK. Tải khóa từ Firebase project của bạn và đặt đường dẫn tương ứng; đường dẫn tương đối được tính từ thư mục chạy lệnh.
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`: thông tin của Cloudinary, cần cho upload ảnh.
- `CORS_ORIGINS`: danh sách origin frontend ở dạng JSON; có thể bỏ dòng này để dùng mặc định trong `config.py`.

Các biến Firebase và Cloudinary cũng cần có giá trị để ứng dụng khởi động. Không commit `.env` hoặc khóa service account; cả hai đã được loại khỏi Git trong `.gitignore`.

### 4. Cài dependency

Từ thư mục gốc của repository, cài theo lockfile:

```powershell
uv sync --frozen
```

Lệnh này tạo môi trường `.venv` và cài dependency của project. Các model BGE-M3 và JinaCLIP v2 được tải từ Hugging Face khi khởi động ứng dụng lần đầu, vì vậy cần kết nối Internet; tải model có thể tốn thời gian và dung lượng đĩa. Ứng dụng chạy được trên CPU, còn tìm kiếm bằng model có thể chậm hơn nếu không có GPU.

### 5. Khởi động API

Chạy từ thư mục gốc để ứng dụng đọc đúng file `.env`:

```powershell
uv run uvicorn web_ban_hang_backend.main:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

Sau khi server khởi động, mở [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) để xem và gọi thử API; tài liệu ReDoc ở [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc). Dừng server bằng `Ctrl+C`. Tùy chọn `--reload` phù hợp khi phát triển cục bộ.

Nếu log báo không nạp được model, server vẫn có thể chạy các API không cần model; các endpoint tìm kiếm văn bản/ảnh trả `503` trong lúc model chưa sẵn sàng. Worker nền thử nạp lại model định kỳ. Nếu ứng dụng không khởi động, trước tiên kiểm tra các biến trong `.env`, đường dẫn Firebase JSON, kết nối PostgreSQL và việc đã cài `pgvector` trên PostgreSQL.

## Sơ đồ hệ thống

### Kiến trúc tổng quan

Client đăng ký/đăng nhập trực tiếp với Firebase Authentication, sau đó gửi Firebase ID token đến API. FastAPI xác thực token bằng Firebase Admin SDK, gọi model tìm kiếm khi cần và đọc/ghi dữ liệu trong PostgreSQL. BGE-M3 và JinaCLIP v2 được nạp trong tiến trình backend; `pgvector` lưu embedding để truy vấn tương đồng.

```mermaid
flowchart LR
    Client["Client web / mobile"]
    Firebase["Firebase Authentication"]
    API["FastAPI backend"]
    Models["Model ML<br/>BGE-M3 · JinaCLIP v2"]
    DB[("PostgreSQL<br/>pgvector")]
    Cloudinary["Cloudinary<br/>ảnh sản phẩm"]

    Client -->|Đăng ký / đăng nhập| Firebase
    Firebase -->|Firebase ID token| Client
    Client -->|HTTPS API · Bearer token| API
    API -->|Firebase Admin SDK<br/>xác thực ID token| Firebase
    API -->|Inference embedding<br/>trong tiến trình backend| Models
    Models -->|Vector 1024 chiều| API
    API -->|SQL và truy vấn vector| DB
    API -->|Upload / xóa ảnh| Cloudinary
```

### ERD — các thực thể và quan hệ chính

ERD dưới đây rút gọn các cột để tập trung vào khóa, quan hệ và dữ liệu quan trọng. Hai trường embedding đang lưu ở `products.semantic_embedding` và `product_images.multimodal_embedding`, mỗi vector có 1024 chiều. Quan hệ nhiều-nhiều giữa người dùng và sản phẩm được triển khai qua `user_favorites`; giỏ hàng và đơn hàng dùng các bảng dòng (`cart_items`, `order_items`) làm bảng liên kết.

```mermaid
erDiagram
    USERS {
        uuid id PK
        string firebase_uid UK
        string email
        string display_name
        string role
        boolean is_active
    }
    CATEGORIES {
        int id PK
        int parent_id FK
        string name
        string slug UK
    }
    PRODUCTS {
        uuid id PK
        int category_id FK
        string name
        string slug UK
        numeric price
        vector semantic_embedding
        tsvector search_vector
    }
    PRODUCT_IMAGES {
        uuid id PK
        uuid product_id FK
        string image_url
        vector multimodal_embedding
        string embedding_status
    }
    CARTS {
        uuid id PK
        uuid user_id FK, UK
    }
    CART_ITEMS {
        uuid id PK
        uuid cart_id FK
        uuid product_id FK
        int quantity
    }
    USER_FAVORITES {
        uuid user_id PK, FK
        uuid product_id PK, FK
    }
    USER_ADDRESSES {
        uuid id PK
        uuid user_id FK
        string receiver_name
        string phone
        string address_line
    }
    ORDERS {
        uuid id PK
        uuid user_id FK
        uuid address_id FK
        numeric total_amount
        string status
    }
    ORDER_ITEMS {
        uuid id PK
        uuid order_id FK
        uuid product_id FK
        string product_name
        int quantity
        numeric price
    }
    PAYMENTS {
        uuid id PK
        uuid order_id FK, UK
        string payment_method
        string status
        numeric amount
    }
    REVIEWS {
        uuid id PK
        uuid user_id FK
        uuid product_id FK
        uuid order_id FK
        int rating
    }

    USERS ||--o| CARTS : owns
    CARTS ||--o{ CART_ITEMS : contains
    PRODUCTS ||--o{ CART_ITEMS : added_to
    USERS ||--o{ USER_FAVORITES : saves
    PRODUCTS ||--o{ USER_FAVORITES : is_favorited
    CATEGORIES o|--o{ CATEGORIES : parent_of
    CATEGORIES o|--o{ PRODUCTS : categorizes
    PRODUCTS ||--o{ PRODUCT_IMAGES : has
    USERS ||--o{ USER_ADDRESSES : has
    USERS ||--o{ ORDERS : places
    USER_ADDRESSES o|--o{ ORDERS : ships_to
    ORDERS ||--o{ ORDER_ITEMS : contains
    PRODUCTS o|--o{ ORDER_ITEMS : referenced_by
    ORDERS ||--o| PAYMENTS : paid_by
    USERS ||--o{ REVIEWS : writes
    PRODUCTS ||--o{ REVIEWS : receives
    ORDERS o|--o{ REVIEWS : associated_with
```

## Danh sách API và chức năng

### 1. Người dùng (Users & Auth)
* **`POST`** `/api/users/sync` - Lưu user từ Firebase vào database (lần đầu đăng nhập).
* **`GET`** `/api/users/me` - Lấy thông tin profile user hiện tại.

### 2. Sản phẩm & Danh mục (Products & Categories)
* **`GET`** `/api/categories` - Lấy danh sách danh mục, có `parent_id` để dựng cây ở frontend.
* **`GET`** `/api/categories/{category_id}` - Lấy thông tin một danh mục theo ID số.
* **`GET`** `/api/products` - Lấy danh sách sản phẩm có phân trang, lọc và sắp xếp.
* **`GET`** `/api/products/search` - Tìm sản phẩm theo chữ bằng embedding và full-text.
* **`POST`** `/api/products/search/image` - Tìm sản phẩm bằng ảnh, có thể kèm từ khóa.
* **`GET`** `/api/products/{id}` - Lấy chi tiết 1 sản phẩm.
* **`CRUD`** `/api/products/{id}/reviews` - Xem/Thêm/Sửa/Xóa đánh giá sản phẩm.

### 3. Giỏ hàng & Yêu thích (Cart & Wishlist)
* **`CRUD`** `/api/cart` - Quản lý giỏ hàng (Xem, Thêm, Sửa số lượng, Xóa sản phẩm).
* **`CRUD`** `/api/users/favorites` - Quản lý danh sách sản phẩm yêu thích (Wishlist).

### 4. Địa chỉ & Đơn hàng (Addresses & Orders)
* **`CRUD`** `/api/users/addresses` - Quản lý sổ địa chỉ giao hàng của user.
* **`CRUD`** `/api/orders` - Quản lý đơn hàng (Tạo đơn mới, Xem lịch sử đơn hàng, Hủy đơn).

### 5. Thanh toán (Payments)
* **`POST`** `/api/orders/{order_id}/pay` - Thanh toán giả lập cho đơn dùng phương thức trực tuyến.
* Thanh toán VNPay/Momo và webhook chưa được tích hợp; đơn COD không dùng endpoint thanh toán giả lập.

### 6. Quản trị viên (Admin - Yêu cầu role 'admin')
* **`CRUD`** `/api/admin/products` - Quản lý sản phẩm và ảnh (`product_images`).
* **`CRUD`** `/api/admin/categories` - Quản lý danh mục.
* **`GET`** `/api/admin/orders` - Xem danh sách toàn bộ đơn hàng.
* **`PATCH`** `/api/admin/orders/{id}/status` - Cập nhật trạng thái đơn hàng (Đang giao, Hoàn thành...).
* **`GET`** `/api/admin/analytics` - Lấy thống kê doanh thu, số đơn bán ra.

## Luồng đăng ký, đăng nhập và đồng bộ profile

Firebase xử lý xác thực tài khoản và cấp ID token. Endpoint `POST /api/users/sync` tạo bản ghi `users` khi `firebase_uid` chưa tồn tại; nếu đã có, backend trả hồ sơ hiện có. `GET /api/users/me` đọc profile trong PostgreSQL và `PUT /api/users/me` cập nhật các trường hồ sơ được hỗ trợ.

### Luồng 1: Đăng nhập / Đồng bộ (`POST /api/auth/sync`)

```mermaid
flowchart TD
    User["Người dùng"] --> Choice{"Đăng ký hay đăng nhập?"}
    Choice -->|Đăng ký| SignUp["Client tạo tài khoản với Firebase"]
    Choice -->|Đăng nhập| SignIn["Client đăng nhập với Firebase"]
    SignUp --> Auth["Firebase Authentication"]
    SignIn --> Auth
    Auth -->|Thất bại| AuthError["Hiển thị lỗi xác thực"] --> END1(["END"])
    Auth -->|Thành công: cấp ID token| Client["Client nhận token"]
    Client -->|"POST /api/auth/sync<br/>Bearer token + profile tùy chọn"| Sync["FastAPI xác thực token<br/>bằng Firebase Admin SDK"]
    Sync --> Valid{"Token hợp lệ?"}
    Valid -->|Không| Unauthorized["401 Unauthorized"] --> END2(["END"])
    Valid -->|Có| Lookup["Tìm users theo firebase_uid"]
    Lookup --> Exists{"Đã có user?"}
    Exists -->|Chưa| Create["Tạo users<br/>role mặc định customer"]
    Exists -->|Rồi| Active{"Tài khoản đang hoạt động?"}
    Active -->|Không| Forbidden["403 Tài khoản bị khóa"] --> END3(["END"])
    Active -->|Có| Existing["Giữ profile PostgreSQL hiện có"]
    Create --> Synced["Trả UserRead + AccessToken"]
    Existing --> Synced
    Synced --> END4(["END"])
```

### Luồng 2: Lấy thông tin cá nhân (`GET /api/users/me`)

```mermaid
flowchart TD
    Client["Client gửi request<br/>GET /api/users/me + Bearer token"] --> Verify["FastAPI xác thực token"]
    Verify --> Valid{"Token hợp lệ?"}
    Valid -->|Không| Unauthorized["401 Unauthorized"] --> END1(["END"])
    Valid -->|Có| Query["Query users theo firebase_uid"]
    Query --> Found{"Tìm thấy user?"}
    Found -->|Không| NotFound["404 Chưa đồng bộ user"] --> END2(["END"])
    Found -->|Có| Active{"Tài khoản đang hoạt động?"}
    Active -->|Không| Forbidden["403 Tài khoản bị khóa"] --> END3(["END"])
    Active -->|Có| Response["Trả UserRead"] --> END4(["END"])
```

### Luồng 3: Cập nhật thông tin (`PUT /api/users/me`)

```mermaid
flowchart TD
    Client["Client gửi body mới<br/>PUT /api/users/me + Bearer token"] --> Verify["FastAPI xác thực token"]
    Verify --> Valid{"Token hợp lệ?"}
    Valid -->|Không| Unauthorized["401 Unauthorized"] --> END1(["END"])
    Valid -->|Có| Validate{"Body hợp lệ?<br/>display_name, phone_number, photo_url"}
    Validate -->|Không| Invalid["422 Dữ liệu không hợp lệ"] --> END2(["END"])
    Validate -->|Có| Update["Cập nhật các trường<br/>display_name, phone_number, photo_url"]
    Update -->|Commit PostgreSQL| Response["Trả UserRead mới"] --> END3(["END"])
```

Khi tạo user lần đầu, email/tên/ảnh được lấy từ token Firebase và tên/số điện thoại có thể được cung cấp trong request sync. Với user đã tồn tại, `/sync` không ghi đè các trường profile; việc sửa tên, số điện thoại hoặc ảnh thực hiện qua `PUT /api/users/me`.

## Pipeline tìm kiếm sản phẩm bằng văn bản và hình ảnh

### Quy tắc chung

Pipeline dùng hai model và hai không gian vector độc lập ([model card BGE-M3](https://huggingface.co/BAAI/bge-m3), [model card JinaCLIP v2](https://huggingface.co/jinaai/jina-clip-v2)):

| Model/kênh | Đầu vào | Không gian và cột lưu |
| --- | --- | --- |
| BGE-M3 (`BAAI/bge-m3`) | Nội dung văn bản sản phẩm và truy vấn chữ | `products.semantic_embedding` |
| JinaCLIP v2 (`jinaai/jina-clip-v2`) | Ảnh sản phẩm, ảnh truy vấn và truy vấn chữ | `product_images.multimodal_embedding` |

- Cả hai loại vector có 1024 chiều, được chuẩn hóa L2. Truy vấn trong `services/search.py` dùng khoảng cách cosine (`cosine_distance`).
- Không bao giờ so sánh hoặc cộng trực tiếp vector BGE-M3 với vector JinaCLIP. Chỉ gộp thứ hạng kết quả của các kênh độc lập.
- Văn bản đưa vào BGE-M3 được dựng từ tên, mô tả và thuộc tính sản phẩm; văn bản truy vấn được encode trực tiếp. JinaCLIP encode ảnh sản phẩm/ảnh truy vấn và văn bản truy vấn vào cùng không gian đa phương thức.
- Ảnh upload và ảnh truy vấn dùng `decode_image_bytes`: chấp nhận JPEG/PNG/WEBP, giới hạn 10 MB và 40 triệu điểm ảnh, áp dụng hướng EXIF rồi chuyển RGB; không crop ảnh.
- `products.search_vector` là cột sinh từ tên và mô tả bằng `to_tsvector('simple', ...)`; không bao gồm thuộc tính sản phẩm.
- FastAPI nạp cả hai model khi khởi động bằng `asyncio.to_thread`. Nếu nạp thất bại, API vẫn khởi động và worker nền định kỳ thử nạp lại. Các endpoint semantic search kiểm tra trạng thái chung của cả hai model và trả `503` nếu một trong hai chưa sẵn sàng, kể cả khi truy vấn chỉ cần BGE-M3 hoặc full-text.
- Route admin tạo/sửa sản phẩm và upload ảnh vẫn lưu dữ liệu khi model chưa sẵn sàng; embedding được đánh dấu `pending` để worker xử lý sau.

Ví dụ khai báo index trong migration PostgreSQL:

```sql
CREATE INDEX ix_products_semantic_embedding_hnsw
    ON products USING hnsw (semantic_embedding vector_cosine_ops);

CREATE INDEX ix_product_images_multimodal_embedding_hnsw
    ON product_images USING hnsw (multimodal_embedding vector_cosine_ops);
```

Các index cosine ở trên khớp với toán tử truy vấn trong code. Trong `db.sql`, hai index HNSW hiện chưa chỉ rõ operator class, vì vậy file dump chưa thể hiện cấu hình `vector_cosine_ops` này.

### Lập chỉ mục sản phẩm và ảnh (admin)

**Sản phẩm — `POST /api/admin/products` và cập nhật sản phẩm**

1. FastAPI kiểm tra `ProductCreate`; dữ liệu không hợp lệ trả `422`.
2. Dựng văn bản theo thứ tự: `Tên`, mô tả nếu có, rồi các thuộc tính theo thứ tự khóa; bỏ giá trị rỗng và nối giá trị list bằng dấu phẩy. Tính SHA-256 trên văn bản này.
3. Nếu vector hiện có cùng hash và model `BGE-m3@1024` còn hiện hành, giữ vector và đặt trạng thái `indexed`. Nếu nội dung cần encode và model sẵn sàng, gọi BGE-M3; khi thành công cập nhật vector, model, hash, thời điểm và trạng thái `indexed`.
4. Nếu cần vector mới nhưng model chưa sẵn sàng, sản phẩm vẫn được lưu với trạng thái `pending`. Nếu encode lỗi, sản phẩm vẫn được lưu với trạng thái `failed` và `embedding_error`. Khi sửa một sản phẩm đã có vector, vector cũ vẫn được giữ trong lúc pending hoặc failed; search hiện lọc theo vector khác `NULL`, không lọc theo `embedding_status`, nên vector cũ vẫn có thể được dùng cho đến khi encode bù thành công.
5. Route là hàm đồng bộ; FastAPI chạy handler và thao tác encode trong threadpool.

**Ảnh — `POST /api/admin/products/{id}/images`**

1. Kiểm tra sản phẩm tồn tại; giới hạn file 10 MB/40 triệu điểm ảnh, chấp nhận JPEG/PNG/WEBP, sửa hướng EXIF và chuyển RGB. Ảnh sai trả `400`, quá lớn trả `413`, định dạng không hỗ trợ trả `415`.
2. Nếu model sẵn sàng, gọi JinaCLIP image encoder và chuẩn hóa vector 1024 chiều. Nếu chưa sẵn sàng, đặt trạng thái `pending`; nếu encode lỗi, đặt `failed` và lưu thông tin lỗi. Cả hai trường hợp vẫn tiếp tục upload ảnh.
3. Upload ảnh lên Cloudinary, rồi ghi `product_images.image_url`, `storage_key` cùng vector và trạng thái tương ứng. Route này không trả `503` chỉ vì model chưa sẵn sàng.
4. Nếu upload thất bại, trả `502`. Nếu ghi DB thất bại sau khi upload, rollback và xóa file vừa tải lên theo `storage_key`.
5. Route là hàm đồng bộ; FastAPI chạy handler và encode trong threadpool.

Worker trong lifespan tự lấy sản phẩm `pending` theo lô 20 và ảnh `pending` theo lô 10; khi đang có việc, lượt kế tiếp chạy sau 2 giây, nếu hết việc thì nghỉ 30 giây. Worker khóa các hàng cần xử lý bằng `FOR UPDATE SKIP LOCKED`. Với ảnh pending, worker tải lại `image_url` (timeout 15 giây), giải mã rồi encode; lỗi tải/encode chuyển ảnh sang `failed` và lưu lỗi. Bản ghi `failed` không tự chạy lại.

Admin có thể gọi `POST /api/admin/embeddings/retry-failed`; endpoint đưa toàn bộ sản phẩm và ảnh `failed` về `pending`, xóa `embedding_error` và trả số lượng từng loại. Nếu URL ảnh đã hỏng/404, cần sửa URL hoặc tải lại ảnh trước khi retry; nếu giữ nguyên URL, lần backfill kế tiếp sẽ thất bại lại. Khi xóa sản phẩm hoặc ảnh, backend commit xóa dòng DB trước rồi gọi Cloudinary xóa file; nếu xóa file lỗi, backend ghi log để dọn thủ công.

> **Lưu ý schema:** backend hiện yêu cầu `products.embedding_status`, `products.embedding_error` và các check constraint trạng thái embedding. Bản `db.sql` trong repository chưa có các cột/constraint này cho bảng `products`; cần cập nhật schema trước khi chạy phiên bản backend có worker backfill.

### Tìm kiếm và hợp nhất kết quả

Có bốn kênh, mỗi kênh lấy tối đa 50 sản phẩm sau khi lọc:

| Kênh | Đầu vào | Model/phép tìm | So với |
| --- | --- | --- | --- |
| A | Ảnh truy vấn | JinaCLIP image encoder; sắp xếp theo `MIN(cosine_distance)` trên ảnh của mỗi sản phẩm | `product_images.multimodal_embedding` |
| B | Chữ truy vấn | JinaCLIP text encoder; sắp xếp theo `MIN(cosine_distance)` trên ảnh của mỗi sản phẩm | `product_images.multimodal_embedding` |
| C | Chữ truy vấn | BGE-M3; sắp xếp theo cosine distance | `products.semantic_embedding` |
| D | Chữ truy vấn | `websearch_to_tsquery` và `ts_rank_cd` | `products.search_vector` |

Chọn kênh theo loại yêu cầu:

- Chỉ ảnh (`POST /api/products/search/image` không có `q` hoặc `q` chỉ có khoảng trắng): A.
- Ảnh kèm chữ: A, B, C, D.
- Chỉ chữ (`GET /api/products/search`): B, C, D.

Kênh D chạy mỗi khi có chữ, không có cờ bật/tắt riêng. `search_vector` được tạo với cấu hình `simple`, còn code gọi `websearch_to_tsquery(query)` mà không truyền cấu hình nên PostgreSQL dùng cấu hình tìm kiếm mặc định cho truy vấn. Kênh A/B/C chỉ truy vấn các vector khác `NULL`; chúng không lọc theo `embedding_status`.

Endpoint public áp dụng `is_active = true`, cùng `category_id`, `min_price`, `max_price` nếu được gửi. Admin có tìm kiếm lai qua `POST /api/admin/products/search/image`; endpoint này hỗ trợ thêm `on_sale` và `is_active` tùy chọn. Admin `GET /api/admin/products` là danh sách/lọc theo tên, không chạy pipeline semantic.

Gộp thứ hạng các kênh bằng Reciprocal Rank Fusion (RRF):

```python
def rrf(rankings: list[list[UUID]], k: int = 60) -> list[UUID]:
    scores: dict[UUID, float] = {}
    for ranking in rankings:  # mỗi kênh là product_id đã sắp theo độ giống
        seen = set()
        for rank, pid in enumerate(ranking, start=1):
            if pid in seen:
                continue
            seen.add(pid)
            scores[pid] = scores.get(pid, 0) + 1 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)
```

Backend giữ tối đa 100 `product_id` sau RRF, sau đó phân trang và trả `Page[ProductRead]` theo đúng thứ tự xếp hạng. Response có ảnh của sản phẩm nhưng không trả riêng ảnh khớp nhất, điểm từng kênh hoặc điểm RRF.

### Sơ đồ pipeline

```mermaid
flowchart TD
    Startup["Lifespan nạp BGE-M3 và JinaCLIP<br/>worker thử nạp lại nếu thất bại"] --> ModelState["Trạng thái model dùng chung"]
    ModelState --> Gate

    subgraph Search["Tìm kiếm"]
        Req["GET /api/products/search?q<br/>POST /api/products/search/image (file; q tùy chọn)<br/>POST /api/admin/products/search/image"] --> Gate{"Cả BGE-M3 và JinaCLIP sẵn sàng?"}
        Gate -->|Chưa| E503["503 Service Unavailable"]
        Gate -->|Có| Route{"Loại request?"}
        Route -->|GET text| TrimText["Trim q"]
        TrimText --> EmptyText{"q còn nội dung?"}
        EmptyText -->|Không| E422Q["422 từ khóa rỗng"]
        EmptyText -->|Có| TextChannels["Chạy B, C, D"]
        Route -->|POST image| File["Đọc field file, tối đa 10 MB"]
        File --> Decode["Giải mã JPEG/PNG/WEBP,<br/>EXIF transpose, RGB; tối đa 40 MP"]
        Decode -->|Ảnh không hợp lệ| EImageQ["400 / 413 / 415"]
        Decode -->|Ảnh hợp lệ| QImg["JinaCLIP encode ảnh"]
        QImg --> HasImageText{"q sau trim có nội dung?"}
        HasImageText -->|Không| ImageOnly["Chỉ ảnh"]
        HasImageText -->|Có| ImageAndText["Ảnh kèm chữ"]
        ImageOnly --> A["A · cosine distance với ảnh sản phẩm;<br/>GROUP BY product_id, MIN(distance), top 50"]
        ImageAndText --> A
        ImageAndText --> TextChannels
        TextChannels --> QJText["JinaCLIP encode_text"]
        TextChannels --> QBGE["BGE-M3 encode text"]
        TextChannels --> FTS["websearch_to_tsquery(query)"]
        QJText --> B["B · cosine distance với ảnh sản phẩm;<br/>GROUP BY product_id, MIN(distance), top 50"]
        QBGE --> C["C · cosine distance với<br/>products.semantic_embedding, top 50"]
        FTS --> D["D · search_vector @@ tsquery,<br/>rank theo ts_rank_cd, top 50"]
        Filters["Lọc sản phẩm theo endpoint:<br/>public is_active=true, category, price;<br/>admin image thêm on_sale/is_active tùy chọn"] --> A
        Filters --> B
        Filters --> C
        Filters --> D
        A --> RRF["RRF (k=60); hợp nhất kênh có kết quả"]
        B --> RRF
        C --> RRF
        D --> RRF
        RRF --> Page["Giữ tối đa top 100 product ID,<br/>sau đó phân trang"]
        Page --> Result["Nạp ProductRead theo thứ hạng;<br/>không trả riêng ảnh khớp nhất hoặc điểm"]
    end
```

`GET /api/products/search` yêu cầu `q` không rỗng sau khi trim. Hai endpoint ảnh yêu cầu file `file`; `q` là field form tùy chọn, rỗng thì bỏ qua. Tìm bằng ảnh không có `q` chỉ chạy A; ảnh kèm chữ chạy A, B, C, D. Cả ba endpoint đều trả `503` nếu một trong hai model chưa sẵn sàng. Nếu encode ảnh truy vấn thất bại, exception làm request thất bại; nếu encode B hoặc C thất bại, backend ghi log và bỏ riêng kênh đó, còn D vẫn chạy. `pending` và `failed` không tự được dùng để lọc khi search: kênh vector xét cột vector khác `NULL`.

### Ví dụ gửi ảnh truy vấn

`POST /api/products/search/image` nhận `multipart/form-data` với field `file` bắt buộc và field `q` tùy chọn. `POST /api/admin/products/search/image` dùng cùng định dạng và thuật toán nhưng yêu cầu quyền admin. Frontend gửi `Blob`/`File` trực tiếp trong `FormData`, không gửi base64 trong JSON:

- Backend kiểm tra dung lượng/nội dung ảnh, chỉ nhận JPEG/PNG/WEBP, áp dụng hướng EXIF và chuyển RGB. Ảnh truy vấn được embed theo request, không lưu thành embedding sản phẩm.
- Endpoint ảnh public trả `400` nếu ảnh rỗng/hỏng, `413` nếu vượt 10 MB hoặc 40 triệu điểm ảnh, `415` nếu định dạng không hỗ trợ; endpoint admin áp dụng cùng giới hạn.
- Nếu có `q` không rỗng, endpoint ảnh chạy thêm B, C và D. Endpoint chữ riêng chạy B, C và D. Cả hai đường đều lấy `page`/`size` qua `fastapi-pagination`.

```javascript
const form = new FormData();
form.append("file", imageBlob, "query.jpg");
form.append("q", "áo khoác màu be, dáng rộng"); // tùy chọn

const response = await fetch("/api/products/search/image", {
  method: "POST",
  body: form,
});
```

Không tự đặt `Content-Type: multipart/form-data`; trình duyệt cần tự thêm multipart boundary.



