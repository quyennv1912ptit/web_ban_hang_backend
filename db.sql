CREATE SCHEMA "public";
CREATE TABLE "cart_items" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"cart_id" uuid NOT NULL,
	"product_id" uuid NOT NULL,
	"quantity" integer DEFAULT 1 NOT NULL,
	"added_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "cart_items_cart_id_product_id_key" UNIQUE("cart_id","product_id"),
	CONSTRAINT "cart_items_quantity_check" CHECK ((quantity > 0))
);
CREATE TABLE "carts" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"user_id" uuid NOT NULL CONSTRAINT "carts_user_id_key" UNIQUE,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "categories" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "categories_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"name" text NOT NULL,
	"slug" text NOT NULL CONSTRAINT "categories_slug_key" UNIQUE,
	"parent_id" integer,
	"icon" text,
	CONSTRAINT "categories_parent_not_self_check" CHECK (((parent_id IS NULL) OR (parent_id <> id)))
);
CREATE TABLE "order_items" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"order_id" uuid NOT NULL,
	"product_id" uuid,
	"product_name" text NOT NULL,
	"quantity" integer NOT NULL,
	"price" numeric(12, 0) NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "order_items_price_check" CHECK ((price >= (0)::numeric)),
	CONSTRAINT "order_items_quantity_check" CHECK ((quantity > 0))
);
CREATE TABLE "orders" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"user_id" uuid NOT NULL,
	"address_id" uuid,
	"total_amount" numeric(12, 0) NOT NULL,
	"shipping_fee" numeric(12, 0) DEFAULT '0' NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"note" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"tracking_code" text,
	"shipping_provider" text,
	"hidden_by_user" boolean DEFAULT false NOT NULL,
	CONSTRAINT "orders_shipping_fee_check" CHECK ((shipping_fee >= (0)::numeric)),
	CONSTRAINT "orders_status_check" CHECK ((status = ANY (ARRAY['pending'::text, 'processing'::text, 'shipped'::text, 'delivered'::text, 'cancelled'::text, 'returned'::text]))),
	CONSTRAINT "orders_total_amount_check" CHECK ((total_amount >= (0)::numeric))
);
CREATE TABLE "payments" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"order_id" uuid NOT NULL CONSTRAINT "payments_order_id_key" UNIQUE,
	"payment_method" text NOT NULL,
	"status" text DEFAULT 'unpaid' NOT NULL,
	"transaction_id" text,
	"amount" numeric(12, 0) NOT NULL,
	"paid_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "payments_amount_check" CHECK ((amount >= (0)::numeric)),
	CONSTRAINT "payments_payment_method_check" CHECK ((payment_method = ANY (ARRAY['cod'::text, 'vnpay'::text, 'momo'::text, 'credit_card'::text]))),
	CONSTRAINT "payments_status_check" CHECK ((status = ANY (ARRAY['unpaid'::text, 'processing'::text, 'completed'::text, 'failed'::text, 'refunded'::text])))
);
CREATE TABLE "product_images" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"product_id" uuid NOT NULL,
	"image_url" text NOT NULL,
	"caption" text,
	"position" integer DEFAULT 0 NOT NULL,
	"multimodal_embedding" vector(1024),
	"storage_key" text,
	"embedding_status" text DEFAULT 'pending' NOT NULL,
	"embedding_model" text,
	"embedding_error" text,
	"indexed_at" timestamp with time zone,
	"original_url" varchar,
	"cropped_url" varchar,
	CONSTRAINT "product_images_product_id_position_key" UNIQUE("product_id","position"),
	CONSTRAINT "product_images_embedding_status_check" CHECK ((embedding_status = ANY (ARRAY['pending'::text, 'indexed'::text, 'failed'::text]))),
	CONSTRAINT "product_images_indexed_has_vector_check" CHECK (((embedding_status <> 'indexed'::text) OR (multimodal_embedding IS NOT NULL))),
	CONSTRAINT "product_images_position_check" CHECK (("position" >= 0))
);
CREATE TABLE "products" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"category_id" integer,
	"name" text NOT NULL,
	"slug" text NOT NULL CONSTRAINT "products_slug_key" UNIQUE,
	"description" text,
	"price" numeric(12, 0) NOT NULL,
	"attributes" jsonb DEFAULT '{}' NOT NULL,
	"search_vector" tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, ((COALESCE(name, ''::text) || ' '::text) || COALESCE(description, ''::text)))) STORED,
	"semantic_embedding" vector(1024),
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"original_price" numeric(12, 0),
	"stock_quantity" integer DEFAULT 0 NOT NULL,
	"sold_count" integer DEFAULT 0 NOT NULL,
	"average_rating" numeric(3, 2) DEFAULT '0.0' NOT NULL,
	"sku" text CONSTRAINT "products_sku_key" UNIQUE,
	"weight_grams" integer DEFAULT 0,
	"embedding_model" text,
	"embedding_text_hash" text,
	"embedding_updated_at" timestamp with time zone,
	CONSTRAINT "products_average_rating_check" CHECK (((average_rating >= (0)::numeric) AND (average_rating <= (5)::numeric))),
	CONSTRAINT "products_check" CHECK ((original_price >= price)),
	CONSTRAINT "products_price_check" CHECK ((price >= (0)::numeric)),
	CONSTRAINT "products_sold_count_check" CHECK ((sold_count >= 0)),
	CONSTRAINT "products_stock_quantity_check" CHECK ((stock_quantity >= 0)),
	CONSTRAINT "products_weight_grams_check" CHECK ((weight_grams >= 0))
);
CREATE TABLE "reviews" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"user_id" uuid NOT NULL,
	"product_id" uuid NOT NULL,
	"order_id" uuid,
	"rating" integer NOT NULL,
	"comment" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "reviews_user_id_product_id_order_id_key" UNIQUE("user_id","product_id","order_id"),
	CONSTRAINT "reviews_rating_check" CHECK (((rating >= 1) AND (rating <= 5)))
);
CREATE TABLE "user_addresses" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"user_id" uuid NOT NULL,
	"receiver_name" text NOT NULL,
	"phone" text NOT NULL,
	"address_line" text NOT NULL,
	"ward" text,
	"district" text,
	"city" text,
	"is_default" boolean DEFAULT false NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "user_favorites" (
	"user_id" uuid,
	"product_id" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "user_favorites_pkey" PRIMARY KEY("user_id","product_id")
);
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
	"firebase_uid" text NOT NULL CONSTRAINT "users_firebase_uid_key" UNIQUE,
	"email" text,
	"display_name" text,
	"role" text DEFAULT 'customer' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"photo_url" text,
	"phone_number" text,
	"is_active" boolean DEFAULT true NOT NULL,
	CONSTRAINT "users_role_check" CHECK ((role = ANY (ARRAY['customer'::text, 'admin'::text])))
);
CREATE UNIQUE INDEX "cart_items_cart_id_product_id_key" ON "cart_items" ("cart_id","product_id");
CREATE UNIQUE INDEX "cart_items_pkey" ON "cart_items" ("id");
CREATE INDEX "idx_cart_items_product" ON "cart_items" ("product_id");
CREATE UNIQUE INDEX "carts_pkey" ON "carts" ("id");
CREATE UNIQUE INDEX "carts_user_id_key" ON "carts" ("user_id");
CREATE UNIQUE INDEX "categories_pkey" ON "categories" ("id");
CREATE UNIQUE INDEX "categories_slug_key" ON "categories" ("slug");
CREATE INDEX "idx_categories_parent" ON "categories" ("parent_id");
CREATE INDEX "idx_order_items_order" ON "order_items" ("order_id");
CREATE INDEX "idx_order_items_product" ON "order_items" ("product_id");
CREATE UNIQUE INDEX "order_items_pkey" ON "order_items" ("id");
CREATE INDEX "idx_orders_address" ON "orders" ("address_id");
CREATE INDEX "idx_orders_status" ON "orders" ("status");
CREATE INDEX "idx_orders_user" ON "orders" ("user_id");
CREATE UNIQUE INDEX "orders_pkey" ON "orders" ("id");
CREATE UNIQUE INDEX "payments_order_id_key" ON "payments" ("order_id");
CREATE UNIQUE INDEX "payments_pkey" ON "payments" ("id");
CREATE INDEX "idx_images_multimodal" ON "product_images" USING hnsw ("multimodal_embedding");
CREATE INDEX "idx_images_pending" ON "product_images" ("embedding_status");
CREATE UNIQUE INDEX "product_images_pkey" ON "product_images" ("id");
CREATE UNIQUE INDEX "product_images_product_id_position_key" ON "product_images" ("product_id","position");
CREATE INDEX "idx_products_active_cat_price" ON "products" ("category_id","price");
CREATE INDEX "idx_products_active_price" ON "products" ("price");
CREATE INDEX "idx_products_attributes" ON "products" USING gin ("attributes");
CREATE INDEX "idx_products_category" ON "products" ("category_id");
CREATE INDEX "idx_products_search" ON "products" USING gin ("search_vector");
CREATE INDEX "idx_products_semantic" ON "products" USING hnsw ("semantic_embedding");
CREATE INDEX "idx_products_unembedded" ON "products" ("id");
CREATE UNIQUE INDEX "products_pkey" ON "products" ("id");
CREATE UNIQUE INDEX "products_sku_key" ON "products" ("sku");
CREATE UNIQUE INDEX "products_slug_key" ON "products" ("slug");
CREATE INDEX "idx_reviews_order" ON "reviews" ("order_id");
CREATE INDEX "idx_reviews_product" ON "reviews" ("product_id");
CREATE UNIQUE INDEX "reviews_pkey" ON "reviews" ("id");
CREATE UNIQUE INDEX "reviews_user_id_product_id_order_id_key" ON "reviews" ("user_id","product_id","order_id");
CREATE INDEX "idx_user_addresses_user" ON "user_addresses" ("user_id");
CREATE UNIQUE INDEX "user_addresses_pkey" ON "user_addresses" ("id");
CREATE INDEX "idx_user_favorites_product" ON "user_favorites" ("product_id");
CREATE UNIQUE INDEX "user_favorites_pkey" ON "user_favorites" ("user_id","product_id");
CREATE UNIQUE INDEX "users_firebase_uid_key" ON "users" ("firebase_uid");
CREATE UNIQUE INDEX "users_pkey" ON "users" ("id");
ALTER TABLE "cart_items" ADD CONSTRAINT "cart_items_cart_id_fkey" FOREIGN KEY ("cart_id") REFERENCES "carts"("id") ON DELETE CASCADE;
ALTER TABLE "cart_items" ADD CONSTRAINT "cart_items_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE CASCADE;
ALTER TABLE "carts" ADD CONSTRAINT "carts_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE;
ALTER TABLE "categories" ADD CONSTRAINT "categories_parent_id_fkey" FOREIGN KEY ("parent_id") REFERENCES "categories"("id") ON DELETE SET NULL;
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "orders"("id") ON DELETE CASCADE;
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE SET NULL;
ALTER TABLE "orders" ADD CONSTRAINT "orders_address_id_fkey" FOREIGN KEY ("address_id") REFERENCES "user_addresses"("id") ON DELETE SET NULL;
ALTER TABLE "orders" ADD CONSTRAINT "orders_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE RESTRICT;
ALTER TABLE "payments" ADD CONSTRAINT "payments_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "orders"("id") ON DELETE CASCADE;
ALTER TABLE "product_images" ADD CONSTRAINT "product_images_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE CASCADE;
ALTER TABLE "products" ADD CONSTRAINT "products_category_id_fkey" FOREIGN KEY ("category_id") REFERENCES "categories"("id") ON DELETE SET NULL;
ALTER TABLE "reviews" ADD CONSTRAINT "reviews_order_id_fkey" FOREIGN KEY ("order_id") REFERENCES "orders"("id") ON DELETE SET NULL;
ALTER TABLE "reviews" ADD CONSTRAINT "reviews_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE CASCADE;
ALTER TABLE "reviews" ADD CONSTRAINT "reviews_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE;
ALTER TABLE "user_addresses" ADD CONSTRAINT "user_addresses_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE;
ALTER TABLE "user_favorites" ADD CONSTRAINT "user_favorites_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE CASCADE;
ALTER TABLE "user_favorites" ADD CONSTRAINT "user_favorites_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE;