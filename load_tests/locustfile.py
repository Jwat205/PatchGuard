from locust import HttpUser, task, between
import random
import jwt
from datetime import datetime, timedelta

JWT_SECRET = "7RNzxvHBUBruMpoNCIVr6NVVDs7NW3dcxsm1qn97wc0"  # ← Use THIS
JWT_ALGO = "HS256"
USER_ID = "test-user"

def generate_test_jwt():
    payload = {
        "sub": USER_ID,
        "exp": datetime.utcnow() + timedelta(minutes=60),
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    return token if isinstance(token, str) else token.decode()


class PatchGuardUser(HttpUser):
    host = "http://127.0.0.1:7000"
    wait_time = between(0.001, 0.005)

    def on_start(self):
        self.token = generate_test_jwt()
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.review_ids = []

    @task(3)
    def list_reviews(self):
        self.client.get("/reviews", headers=self.headers, name="/reviews")

    @task(2)
    def get_single_review(self):
        if not self.review_ids:
            return

        review_id = random.choice(self.review_ids)
        self.client.get(
            f"/reviews/{review_id}",
            headers=self.headers,
            name="/reviews/{review_id}",
        )
