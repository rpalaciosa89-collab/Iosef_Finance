from app.core.security import verify_password
hashed = "$2b$12$FXSMFVdqJ3nAhsve2BzgMulCPfqC4K.8THjYfWyiulppCljYt0b8O"
for pwd in ["admin123", "password", "iosef123", "admin", "123456", "Iosef2026!"]:
    if verify_password(pwd, hashed):
        print(f"Password is: {pwd}")
        break
else:
    print("Not found in common list.")
