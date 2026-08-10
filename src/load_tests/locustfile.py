from locust import HttpUser, between, task


class LoadTest(HttpUser):
    wait_time = between(0.001, 0.005)

    @task
    def ping(self):
        self.client.get("/ping")
