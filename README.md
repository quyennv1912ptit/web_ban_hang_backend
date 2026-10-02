# Danh sách API E-commerce (Single-Vendor)

## 1. Người dùng (Users & Auth)
* **`POST`** `/api/users/sync` - Lưu user từ Firebase vào database (lần đầu đăng nhập).
* **`GET`** `/api/users/me` - Lấy thông tin profile user hiện tại.

## 2. Sản phẩm & Danh mục (Products & Categories)
* **`GET`** `/api/categories` - Lấy danh sách cây danh mục (hiển thị menu).
* **`GET`** `/api/categories/{slug}` - Lấy thông tin danh mục và sản phẩm bên trong.
* **`GET`** `/api/products` - Lấy danh sách sản phẩm (có phân trang, search, filter).
* **`GET`** `/api/products/{id}` - Lấy chi tiết 1 sản phẩm.
* **`CRUD`** `/api/products/{id}/reviews` - Xem/Thêm/Sửa/Xóa đánh giá sản phẩm.

## 3. Giỏ hàng & Yêu thích (Cart & Wishlist)
* **`CRUD`** `/api/cart` - Quản lý giỏ hàng (Xem, Thêm, Sửa số lượng, Xóa sản phẩm).
* **`CRUD`** `/api/users/favorites` - Quản lý danh sách sản phẩm yêu thích (Wishlist).

## 4. Địa chỉ & Đơn hàng (Addresses & Orders)
* **`CRUD`** `/api/users/addresses` - Quản lý sổ địa chỉ giao hàng của user.
* **`CRUD`** `/api/orders` - Quản lý đơn hàng (Tạo đơn mới, Xem lịch sử đơn hàng, Hủy đơn).

## 5. Thanh toán (Payments)
* **`POST`** `/api/payments/create` - Khởi tạo giao dịch (trả về URL thanh toán VNPay/Momo...).
* **`POST`** `/api/payments/webhook` - Nhận callback từ cổng thanh toán để cập nhật trạng thái.

## 6. Quản trị viên (Admin - Yêu cầu role 'admin')
* **`CRUD`** `/api/admin/products` - Quản lý sản phẩm và ảnh (`product_images`).
* **`CRUD`** `/api/admin/categories` - Quản lý danh mục.
* **`GET`** `/api/admin/orders` - Xem danh sách toàn bộ đơn hàng.
* **`PATCH`** `/api/admin/orders/{id}/status` - Cập nhật trạng thái đơn hàng (Đang giao, Hoàn thành...).
* **`GET`** `/api/admin/analytics` - Lấy thống kê doanh thu, số đơn bán ra.

xxxbase field dùng chung
xxxcreate body của post
xxxupdate body của patch
xxxread body trả về cho client -- bỏ field nhạy cảm và nội bộ
xxxlistitme trả vè danh sách 
xxxdetail kế thừa listitem và thêm quan hệ lồng nhau