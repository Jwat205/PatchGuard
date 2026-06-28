from locust import HttpUser, task, between

class LoadTest(HttpUser):
    wait_time = between(0.001, 0.005)

    @task
    def ping(self):
        self.client.get("/health/ping")
