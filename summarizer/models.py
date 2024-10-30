from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class VideoSummary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    youtube_title = models.CharField(max_length=200)
    youtube_link = models.URLField()
    summary_content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.youtube_title} - {self.user.username}"
