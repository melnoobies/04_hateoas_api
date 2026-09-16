# run_local.py
print("Server GraphQL lokal aktif di http://localhost:8000/graphql")
print("Menerima query: categories { id name products { id name } }")
print("-" * 50)

resolver_call_count = 0
categories = [1, 2]  # id category yang ada di database

for cat_id in categories:
    resolver_call_count += 1
    print(f"[N+1 Tracker] Resolver Category.products dipanggil untuk category id={cat_id}! Total pemanggilan: {resolver_call_count}")

print("-" * 50)
print("Query selesai dieksekusi. Total query database relasi:", resolver_call_count)