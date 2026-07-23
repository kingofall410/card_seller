from django.db import models

class ListingSpread(models.TextChoices):
    
    #card
    NONE = "none", "None"
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    DAILY_2X = "2x daily", "2x Daily"
    DAILY_10X = "10x daily", "10x Daily"