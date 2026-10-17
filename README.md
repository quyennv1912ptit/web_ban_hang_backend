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

## Cấu trúc chính

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

Nếu log báo không nạp được model, server vẫn có thể chạy các API không cần model, nhưng các endpoint tìm kiếm văn bản/ảnh trả `503` cho đến khi model được tải thành công. Nếu ứng dụng không khởi động, trước tiên kiểm tra các biến trong `.env`, đường dẫn Firebase JSON, kết nối PostgreSQL và việc đã cài `pgvector` trên PostgreSQL.

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
- Embedding sản phẩm được tính khi admin tạo/sửa sản phẩm. Embedding truy vấn chỉ được tính khi có yêu cầu tìm kiếm.
- Nạp hai model đúng một lần trong FastAPI lifespan. Nếu model chưa sẵn sàng, endpoint cần model trả `503`.

Ví dụ khai báo index trong migration PostgreSQL:

```sql
CREATE INDEX ix_products_semantic_embedding_hnsw
    ON products USING hnsw (semantic_embedding vector_cosine_ops);

CREATE INDEX ix_product_images_multimodal_embedding_hnsw
    ON product_images USING hnsw (multimodal_embedding vector_cosine_ops);
```

#### 7.2. Lập chỉ mục sản phẩm và ảnh (admin)

**Sản phẩm — `POST /api/admin/products` và cập nhật sản phẩm**

1. Admin gửi dữ liệu; backend kiểm tra hợp lệ rồi lưu bản ghi vào `products`.
2. Dựng văn bản ổn định từ các trường tìm kiếm, ví dụ `Tên: ... Mô tả: ... Màu sắc: ...`, rồi tính hash của chuỗi đó.
3. Chỉ khi hash khác `embedding_text_hash` (hoặc model lưu hiện tại đã cũ), gọi BGE-M3. Chuẩn hóa vector và ghi `semantic_embedding`, `embedding_model`, `embedding_text_hash`, `embedding_updated_at`.
4. Nếu nội dung không đổi và model vẫn hiện hành, giữ vector hiện có, không gọi lại BGE-M3.

**Ảnh — `POST /api/admin/products/{id}/images`**

1. Kiểm tra giới hạn dung lượng, giải mã ảnh thật (không tin tên file hoặc MIME do client gửi) và chuyển ảnh sang RGB.
2. Khi model sẵn sàng, gọi JinaCLIP image encoder với cùng tiền xử lý như ảnh truy vấn và chuẩn hóa vector 1024 chiều.
3. Upload ảnh lên Cloudinary; lưu URL trong `image_url` và khóa file trong `storage_key`.
4. Ghi `product_images` cùng model và trạng thái embedding. Nếu model chưa sẵn sàng, ảnh được lưu ở trạng thái `pending`.
5. Nếu encode lỗi, vẫn lưu ảnh với `embedding_status = 'failed'` và `embedding_error`.
6. Nếu ghi DB lỗi sau khi upload, xóa file vừa upload theo `storage_key`.

Giai đoạn đầu, thực hiện đồng bộ trong request để đơn giản. Khi thời gian xử lý trở thành vấn đề, chuyển công việc embedding sang `BackgroundTasks` hoặc worker. Một job backfill/retry cần quét ảnh có `embedding_status <> 'indexed'` và sản phẩm có hash lệch hoặc `embedding_model` cũ.

#### 7.3. Tìm kiếm và hợp nhất kết quả

Có bốn kênh tìm kiếm. Mỗi kênh lấy khoảng 50 ứng viên sau khi áp dụng `is_active`, category và khoảng giá:

| Kênh | Đầu vào | Model/phép tìm | So với |
| --- | --- | --- | --- |
| A | Ảnh truy vấn | JinaCLIP image encoder | `product_images.multimodal_embedding` |
| B | Chữ truy vấn | JinaCLIP text encoder | `product_images.multimodal_embedding` |
| C | Chữ truy vấn | BGE-M3 | `products.semantic_embedding` |
| D | Chữ truy vấn | `plainto_tsquery` (tùy chọn) | `products.search_vector` |

Chọn kênh theo loại yêu cầu:

- Chỉ ảnh (`POST /api/products/search/image` không có `q`): A.
- Ảnh kèm chữ: A, B, C; thêm D nếu bật tìm kiếm full-text.
- Chỉ chữ (`GET /api/products/search` hoặc endpoint tìm kiếm chữ khác): B, C, D.

Ở kênh A và B, một sản phẩm có thể có nhiều ảnh. Trước khi xếp hạng sản phẩm, gom kết quả ảnh về một dòng cho mỗi `product_id` bằng cách giữ ảnh giống nhất, chẳng hạn `DISTINCT ON (product_id)` hoặc `MIN(distance) GROUP BY product_id`.

Gộp thứ hạng các kênh bằng Reciprocal Rank Fusion (RRF):

```python
def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:  # mỗi kênh là product_id đã sắp theo độ giống
        for rank, pid in enumerate(ranking, start=1):
            scores[pid] = scores.get(pid, 0) + 1 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)
```

Phân trang sau khi gộp: lấy khoảng top 100 sản phẩm theo RRF rồi mới cắt trang. Cuối cùng join `products` và trả sản phẩm, ảnh khớp nhất cùng điểm nếu muốn công khai điểm.

#### 7.4. Sơ đồ pipeline

```mermaid
flowchart TD
    subgraph Models["Vòng đời model"]
        Start["FastAPI lifespan"] --> Load["Nạp BGE-M3 và JinaCLIP một lần"]
        Load --> Ready{"Model sẵn sàng?"}
        Ready -- "Chưa" --> E503["Endpoint cần model trả 503"]
    end

    subgraph Admin["Admin lập chỉ mục — xử lý đồng bộ ban đầu"]
        P["POST /api/admin/products hoặc cập nhật"] --> PV["Validate và lưu products"]
        PV --> Text["Dựng Tên / Mô tả / Màu sắc và tính hash"]
        Text --> Hash{"Hash khác hoặc model cũ?"}
        Hash -- "Có" --> BGE["BGE-M3 → normalize 1024"]
        BGE --> PVec["Lưu semantic_embedding, model, hash, updated_at"]
        Hash -- "Không" --> Keep["Giữ embedding hiện có"]

        I["POST /api/admin/products/{id}/images"] --> Check["Giới hạn dung lượng, giải mã thật, RGB"]
        Check --> Store["Upload storage → original_url + storage_key"]
        Store --> JImg["JinaCLIP image → normalize 1024"]
        JImg --> IRow["Ghi product_images với status indexed"]
        JImg -. "Encode lỗi" .-> Failed["Ghi status failed + embedding_error"]
        IRow -. "Ghi DB lỗi" .-> Cleanup["Xóa file theo storage_key"]
        Failed -. "Ghi DB lỗi" .-> Cleanup
    end

    subgraph Search["Tìm kiếm"]
        Req["Request: ảnh và/hoặc q"] --> Gate{"Model sẵn sàng?"}
        Gate -- "Chưa" --> E503
        Gate -- "Có" --> Kind{"Có ảnh? Có chữ?"}
        Kind -- "Ảnh" --> QImg["JinaCLIP image encoder"]
        Kind -- "Ảnh + chữ" --> QImg
        QImg --> A["A · ảnh → product_images"]
        Kind -- "Chữ" --> QJText["JinaCLIP text encoder"]
        Kind -- "Ảnh + chữ" --> QJText
        QJText --> B["B · chữ → product_images"]
        Kind -- "Chữ" --> QBGE["BGE-M3 text encoder"]
        Kind -- "Ảnh + chữ" --> QBGE
        QBGE --> C["C · chữ → products"]
        Kind -- "Chữ + D bật" --> D["D · plainto_tsquery → search_vector"]
        Kind -- "Ảnh + chữ + D bật" --> D
        A --> Filter["Mỗi kênh: khoảng 50 ứng viên; is_active, category, giá"]
        B --> Filter
        C --> Filter
        D --> Filter
        Filter --> Group["A/B: gom theo product_id, giữ ảnh gần nhất"]
        Group --> RRF["RRF hợp nhất thứ hạng"]
        RRF --> Page["Giữ top 100 rồi phân trang"]
        Page --> Result["Join products; trả ảnh khớp nhất và điểm tùy chọn"]
    end

    Ready -- "Có" --> Admin
    Ready -- "Có" --> Search
```

#### 7.5. Ví dụ gửi ảnh truy vấn

`POST /api/products/search/image` nhận `multipart/form-data` với field `file` và field `q` tùy chọn. Frontend gửi `Blob`/`File` trực tiếp trong `FormData`, không gửi base64 trong JSON:

- Backend kiểm tra dung lượng và giải mã nội dung ảnh thật, chuyển RGB, rồi áp dụng đúng tiền xử lý ảnh đã dùng khi lập chỉ mục. Không tin tên file hoặc MIME client gửi.
- Ảnh truy vấn được embed theo request và không lưu thành embedding sản phẩm. Nếu có `q`, chạy thêm các kênh chữ B và C (cùng D nếu bật); nếu không có ảnh thì dùng B, C, D.

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

