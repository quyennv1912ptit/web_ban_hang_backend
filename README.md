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

Nếu log báo không nạp được model, server vẫn có thể chạy các API không cần model, nhưng các endpoint tìm kiếm văn bản/ảnh trả `503` cho đến khi model được tải thành công. Nếu ứng dụng không khởi động, trước tiên kiểm tra các biến trong `.env`, đường dẫn Firebase JSON, kết nối PostgreSQL và việc đã cài `pgvector` trên PostgreSQL.

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

### Luồng đăng ký, đăng nhập và đồng bộ profile

Firebase xử lý xác thực tài khoản và cấp ID token. Endpoint `POST /api/users/sync` tạo bản ghi `users` khi `firebase_uid` chưa tồn tại; nếu đã có, backend trả hồ sơ hiện có. `GET /api/users/me` đọc profile trong PostgreSQL và `PUT /api/users/me` cập nhật các trường hồ sơ được hỗ trợ.

```mermaid
flowchart TD
    User["Người dùng"] --> Choice{"Đăng ký hay đăng nhập?"}
    Choice -->|Đăng ký| SignUp["Client tạo tài khoản với Firebase"]
    Choice -->|Đăng nhập| SignIn["Client đăng nhập với Firebase"]
    SignUp --> Auth["Firebase Authentication"]
    SignIn --> Auth
    Auth -->|Thành công: cấp ID token| Client["Client nhận token"]
    Auth -->|Thất bại| AuthError["Hiển thị lỗi xác thực"]
    Client -->|POST /api/users/sync<br/>Bearer token + profile tùy chọn| Sync["FastAPI xác thực token<br/>bằng Firebase Admin SDK"]
    Sync --> Valid{"Token hợp lệ?"}
    Valid -->|Không| Unauthorized["401 Unauthorized"]
    Valid -->|Có| Lookup["Tìm users theo firebase_uid"]
    Lookup --> Exists{"Đã có user?"}
    Exists -->|Chưa| Create["Tạo users<br/>role mặc định customer"]
    Exists -->|Rồi| Active{"Tài khoản đang hoạt động?"}
    Active -->|Không| Forbidden["403 Tài khoản bị khóa"]
    Active -->|Có| Existing["Giữ profile PostgreSQL hiện có"]
    Create --> Synced["Trả UserRead"]
    Existing --> Synced
    Synced -->|GET /api/users/me| GetProfile["Đọc profile hiện tại"]
    GetProfile --> Edit{"Có chỉnh sửa profile?"}
    Edit -->|Không| Response["Trả profile cho client"]
    Edit -->|Có · PUT /api/users/me| UpdateProfile["Cập nhật display_name,<br/>phone_number, photo_url"]
    UpdateProfile -->|Commit PostgreSQL| Response
```

Khi tạo user lần đầu, email/tên/ảnh được lấy từ token Firebase và tên/số điện thoại có thể được cung cấp trong request sync. Với user đã tồn tại, `/sync` không ghi đè các trường profile; việc sửa tên, số điện thoại hoặc ảnh thực hiện qua `PUT /api/users/me`.

### 7. Pipeline tìm kiếm sản phẩm bằng văn bản và hình ảnh

#### 7.1. Quy tắc chung

Pipeline dùng hai model và hai không gian vector độc lập ([model card BGE-M3](https://huggingface.co/BAAI/bge-m3), [model card JinaCLIP v2](https://huggingface.co/jinaai/jina-clip-v2)):

| Model/kênh | Đầu vào | Không gian và cột lưu |
| --- | --- | --- |
| BGE-M3 | Văn bản sản phẩm và truy vấn chữ | `products.semantic_embedding` |
| JinaCLIP v2 | Ảnh sản phẩm, ảnh truy vấn và văn bản truy vấn | `product_images.multimodal_embedding` |

- Cả hai loại vector có 1024 chiều, được chuẩn hóa L2 và so sánh bằng cosine. Tạo HNSW index với `vector_cosine_ops` cho từng cột vector.
- Không bao giờ so sánh hoặc cộng trực tiếp vector BGE-M3 với vector JinaCLIP. Chỉ gộp thứ hạng kết quả của các kênh độc lập.
- Ảnh sản phẩm và ảnh truy vấn dùng cùng tiền xử lý: giải mã ảnh, chuyển RGB và thống nhất dùng ảnh gốc hoặc cùng quy tắc crop.
- Backend thử tính embedding sản phẩm khi admin tạo/sửa sản phẩm; embedding truy vấn chỉ được tính khi có yêu cầu tìm kiếm.
- FastAPI lifespan nạp hai model một lần bằng `asyncio.to_thread`. Nếu nạp lỗi, ứng dụng vẫn khởi động với trạng thái model chưa sẵn sàng; các endpoint tìm kiếm hiện kiểm tra trạng thái và trả `503`.
- Route tạo/sửa sản phẩm không trả `503` khi model chưa sẵn sàng: backend lưu sản phẩm và bỏ qua việc tạo embedding mới. Upload ảnh vẫn tiếp tục và lưu ảnh với `embedding_status = 'pending'`.

Ví dụ khai báo index trong migration PostgreSQL:

```sql
CREATE INDEX ix_products_semantic_embedding_hnsw
    ON products USING hnsw (semantic_embedding vector_cosine_ops);

CREATE INDEX ix_product_images_multimodal_embedding_hnsw
    ON product_images USING hnsw (multimodal_embedding vector_cosine_ops);
```

#### 7.2. Lập chỉ mục sản phẩm và ảnh (admin)

**Sản phẩm — `POST /api/admin/products` và cập nhật sản phẩm**

1. FastAPI kiểm tra `ProductCreate`; dữ liệu không hợp lệ trả `422`.
2. Dựng văn bản từ `name`, `description` và `attributes` (theo thứ tự khóa ổn định, bỏ giá trị rỗng), rồi tính SHA-256.
3. Nếu vector hiện có cùng hash và model `BGE-m3@1024` vẫn hiện hành, giữ vector. Nếu cần làm mới và model sẵn sàng, gọi BGE-M3; khi thành công cập nhật `semantic_embedding`, `embedding_model`, `embedding_text_hash`, `embedding_updated_at`.
4. Nếu model chưa sẵn sàng hoặc encode lỗi, request vẫn tiếp tục lưu sản phẩm. Encode lỗi được ghi log; schema hiện không có trạng thái reindex riêng cho embedding sản phẩm. Khi cập nhật, vector cũ có thể vẫn còn dù nội dung mới đã thay đổi.
5. Route là hàm đồng bộ; FastAPI chạy handler và thao tác encode trong threadpool.

**Ảnh — `POST /api/admin/products/{id}/images`**

1. Kiểm tra sản phẩm tồn tại; sau đó giới hạn file 10 MB, giải mã nội dung JPEG/PNG/WEBP và chuyển sang RGB. Lỗi ảnh trả `400`, `413` hoặc `415` tùy nguyên nhân.
2. Nếu model sẵn sàng, gọi JinaCLIP image encoder và chuẩn hóa vector 1024 chiều. Nếu chưa sẵn sàng, giữ trạng thái `pending`; nếu encode lỗi, đặt `failed` và lưu thông tin lỗi.
3. Upload ảnh lên Cloudinary, rồi ghi `product_images.image_url`, `storage_key` cùng vector và trạng thái tương ứng. Route này không trả `503` chỉ vì model chưa sẵn sàng.
4. Nếu upload thất bại, trả `502`. Nếu ghi DB thất bại sau khi upload, rollback và xóa file vừa tải lên theo `storage_key`.
5. Route là hàm đồng bộ; FastAPI chạy handler và encode trong threadpool.

Hiện chưa có endpoint `/api/admin/reindex` hoặc job nền để chạy lại embedding. Ảnh `pending`/`failed` không tự được thử lại; cần xóa và tải lại ảnh hoặc bổ sung job reindex. Embedding sản phẩm thiếu/cũ cũng không tự được tạo lại, nhưng có thể kích hoạt lại bằng thao tác cập nhật sản phẩm khi model sẵn sàng. Khi xóa sản phẩm hoặc ảnh, backend commit xóa dòng DB trước rồi gọi Cloudinary xóa file; nếu xóa file lỗi, backend ghi log để dọn thủ công.

#### 7.3. Tìm kiếm và hợp nhất kết quả

Có bốn kênh tìm kiếm. Mỗi kênh lấy tối đa 50 sản phẩm sau khi áp dụng các bộ lọc phù hợp (`is_active`, category, khoảng giá; tìm kiếm admin còn hỗ trợ lọc khuyến mãi):

| Kênh | Đầu vào | Model/phép tìm | So với |
| --- | --- | --- | --- |
| A | Ảnh truy vấn | JinaCLIP image encoder | `product_images.multimodal_embedding` |
| B | Chữ truy vấn | JinaCLIP text encoder | `product_images.multimodal_embedding` |
| C | Chữ truy vấn | BGE-M3 | `products.semantic_embedding` |
| D | Chữ truy vấn | `websearch_to_tsquery` (luôn chạy khi có chữ) | `products.search_vector` |

Chọn kênh theo loại yêu cầu:

- Chỉ ảnh (`POST /api/products/search/image` không có `q`): A.
- Ảnh kèm chữ: A, B, C, D.
- Chỉ chữ (`GET /api/products/search`): B, C, D.

Kênh A và B thực hiện `GROUP BY product_id`, sắp xếp theo khoảng cách nhỏ nhất (`MIN(distance)`) của ảnh thuộc sản phẩm, rồi lấy tối đa 50 sản phẩm. Kênh C và D cũng lấy tối đa 50 sản phẩm. D chạy cho mọi truy vấn có chữ; code dùng `websearch_to_tsquery`, không có cờ bật/tắt riêng.

Gộp thứ hạng các kênh bằng Reciprocal Rank Fusion (RRF):

```python
def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:  # mỗi kênh là product_id đã sắp theo độ giống
        for rank, pid in enumerate(ranking, start=1):
            scores[pid] = scores.get(pid, 0) + 1 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)
```

Phân trang sau khi gộp: giữ tối đa top 100 product ID theo RRF rồi mới phân trang và nạp các bản ghi `ProductRead`. Response có danh sách ảnh của sản phẩm nhưng hiện không trả riêng ảnh khớp nhất hoặc điểm tương đồng.

#### 7.4. Sơ đồ pipeline

```mermaid
flowchart TD
    subgraph Models["Vòng đời model"]
        Start["FastAPI lifespan"] --> Load["Nạp BGE-M3 và JinaCLIP một lần<br/>asyncio.to_thread"]
        Load -->|Thành công| Ready["model_state.ready = true"]
        Load -. "Lỗi; API vẫn khởi động" .-> NotReady["model_state = None"]
    end

    subgraph Admin["Admin lập chỉ mục — route đồng bộ, chạy trong threadpool"]
        P["POST /api/admin/products<br/>hoặc PUT /api/admin/products/{id}"] --> PV{"ProductCreate hợp lệ?"}
        PV -->|Không| E422A["422 dữ liệu sản phẩm sai"]
        PV -->|Có| Text["Dựng text từ name, description,<br/>attributes; tính SHA-256"]
        Text --> Hash{"Vector đúng hash<br/>và model hiện hành?"}
        Hash -->|Có| Keep["Giữ embedding hiện có"]
        Hash -->|Không| PReady{"Model sẵn sàng?"}
        Ready --> PReady
        NotReady --> PReady
        PReady -->|Có| BGE["BGE-M3 encode<br/>normalize 1024"]
        PReady -->|Chưa| PSkip["Bỏ encode; tiếp tục lưu"]
        BGE -->|Thành công| PVec["Cập nhật semantic_embedding,<br/>model, hash, updated_at"]
        BGE -. "Encode lỗi: log và tiếp tục" .-> PFail["Không cập nhật embedding mới"]
        Keep --> SaveProduct["Commit products"]
        PSkip --> SaveProduct
        PVec --> SaveProduct
        PFail --> SaveProduct
        SaveProduct --> ProductOK["Trả ProductRead<br/>201 tạo mới / 200 cập nhật"]

        I["POST /api/admin/products/{id}/images"] --> Exists{"Sản phẩm tồn tại?"}
        Exists -->|Không| E404I["404 không tìm thấy sản phẩm"]
        Exists -->|Có| Check["Giới hạn 10 MB, giải mã JPEG/PNG/WEBP,<br/>chuyển RGB"]
        Check --> ImageValid{"Ảnh hợp lệ?"}
        ImageValid -->|Không| EImage["400 / 413 / 415"]
        ImageValid -->|Có| IReady{"Model sẵn sàng?"}
        Ready --> IReady
        NotReady --> IReady
        IReady -->|Có| JImg["JinaCLIP image encode<br/>normalize 1024"]
        IReady -->|Chưa| Pending["embedding_status = pending"]
        JImg -->|Thành công| Indexed["embedding_status = indexed"]
        JImg -. "Encode lỗi" .-> Failed["embedding_status = failed<br/>lưu embedding_error"]
        Indexed --> Upload["Upload ảnh lên Cloudinary"]
        Pending --> Upload
        Failed --> Upload
        Upload --> UploadOK{"Upload thành công?"}
        UploadOK -->|Không| E502["502 upload thất bại"]
        UploadOK -->|Có| IRow["Ghi product_images:<br/>image_url, storage_key, vector, status"]
        IRow -->|Commit thành công| IOK["Trả ProductImageRead"]
        IRow -. "Ghi DB lỗi" .-> Cleanup["Rollback và xóa file Cloudinary<br/>theo storage_key"]

        Del["DELETE sản phẩm hoặc ảnh"] --> DelDB["Commit xóa dòng DB<br/>xóa sản phẩm sẽ cascade ảnh"]
        DelDB --> DelFile["Xóa file Cloudinary<br/>theo storage_key"]
        DelFile -. "Xóa file lỗi" .-> DelLog["Ghi log; cần dọn thủ công"]
    end

    subgraph Search["Tìm kiếm"]
        Req["GET /api/products/search?q<br/>POST /api/products/search/image (file; q tùy chọn)<br/>Admin cũng có POST tìm bằng ảnh"] --> Gate{"Model sẵn sàng?"}
        Ready --> Gate
        NotReady --> Gate
        Gate -->|Chưa| E503["503 Service Unavailable"]
        Gate -->|Có| Route{"Loại request?"}
        Route -->|GET tìm bằng chữ| TextValid{"q sau trim có nội dung?"}
        TextValid -->|Không| E422Q["422 từ khóa rỗng"]
        TextValid -->|Có| QJText["JinaCLIP text encoder"]
        Route -->|POST tìm bằng ảnh| Decode["Giải mã ảnh truy vấn, chuyển RGB"]
        Decode -->|Ảnh không hợp lệ| EImageQ["400 / 413 / 415"]
        Decode -->|Ảnh hợp lệ| QImg["JinaCLIP image encoder"]
        QImg --> A["A · SQL trên product_images:<br/>lọc + GROUP BY product_id,<br/>MIN(distance), top 50"]
        QImg --> HasImageText{"q ảnh có nội dung?"}
        QJText --> B["B · SQL trên product_images:<br/>lọc + GROUP BY product_id,<br/>MIN(distance), top 50"]
        HasImageText -->|Có| QJText
        HasImageText -->|Có| QBGE["BGE-M3 text encoder"]
        HasImageText -->|Có| D["D · SQL trên search_vector:<br/>websearch_to_tsquery, top 50"]
        TextValid -->|Có| QBGE
        TextValid -->|Có| D
        QBGE --> C["C · SQL trên products.semantic_embedding,<br/>top 50"]
        A --> RRF["RRF hợp nhất các kênh đang có"]
        B --> RRF
        C --> RRF
        D --> RRF
        RRF --> Page["Giữ tối đa top 100 product ID,<br/>sau đó phân trang"]
        Page --> Result["Nạp ProductRead theo thứ hạng;<br/>không trả riêng ảnh khớp nhất hoặc điểm"]
    end
```

`GET /api/products/search` chạy các kênh B, C, D; tìm bằng ảnh không có `q` chỉ chạy A; ảnh kèm `q` chạy A, B, C, D. Kênh D luôn chạy khi có chữ, không có tùy chọn bật/tắt. Các truy vấn áp dụng bộ lọc sản phẩm tương ứng (`is_active`, category, khoảng giá; admin còn có khuyến mãi). Nếu encode văn bản lỗi, kênh đó được ghi log và bỏ qua; lỗi encode ảnh truy vấn được đẩy lên và không có fallback riêng. Hiện không có route/job reindex; embedding `pending`/`failed` hoặc bị cũ không tự động được tạo lại.

#### 7.5. Ví dụ gửi ảnh truy vấn

`POST /api/products/search/image` nhận `multipart/form-data` với field `file` và field `q` tùy chọn. Frontend gửi `Blob`/`File` trực tiếp trong `FormData`, không gửi base64 trong JSON:

- Backend kiểm tra dung lượng và giải mã nội dung ảnh thật, chuyển RGB, rồi áp dụng đúng tiền xử lý ảnh đã dùng khi lập chỉ mục. Không tin tên file hoặc MIME client gửi.
- Ảnh truy vấn được embed theo request và không lưu thành embedding sản phẩm. Endpoint ảnh yêu cầu field `file`; nếu có `q` không rỗng, chạy thêm B, C và D. Endpoint chữ riêng chạy B, C và D.

```javascript
const form = new FormData();
form.append("file", imageBlob, "query.jpg");
form.append("q", "áo khoác màu be, dáng rộng"); // tùy chọn

const response = await fetch("/api/products/search/image", {
  method: "POST",
  body: form,
  headers: { Authorization: `Bearer ${token}` },
});
```

Không tự đặt `Content-Type: multipart/form-data`; trình duyệt cần tự thêm multipart boundary.

## Cấu trúc thư mục (tham khảo)

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

