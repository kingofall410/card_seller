from django.db import models

class StatusBase(models.TextChoices):
    
    #card
    IMPORTED = "imported", "Imported"
    IDED = "identified", "Identified"
    AUTO_PRICED = "auto-priced", "Auto-Priced"
    PRICED = "priced", "Priced"
    LISTED = "listed", "Listed"
    HELD = "held","Held"
    #pending, failed

    #task
    RUNNING = "running", "Running"
    STAGED = "staged", "Staged" 
    PENDING = "pending", "Pending"
    FAILED = "failed", "Failed"
    SUCCESS = "success", "Success"

    #collection
    #imported, ided, priced, listed
    CLOSED = "closed", "Closed"

    @classmethod
    def get_id(cls, value):
        return StatusBase.values.index(value)

    @classmethod
    def get_meta(cls, value):
        #print(value)
        return {
            cls.IMPORTED: {"icon": "🚫", "color": "#ffffff"},
            cls.IDED: {"icon": "✋", "color": "#fffbe6"},
            cls.STAGED: {"icon": "✋", "color": "#fffbe6"},
            cls.PRICED: {"icon": "$", "color": "#fff1f0"},
            cls.AUTO_PRICED: {"icon": "🤖", "color": "#fff1f0"},
            cls.LISTED: {"icon": "", "color": "#f6ffed"},
            cls.RUNNING: {"icon": "✔️", "color": "#ff0000"},
            cls.PENDING: {"icon": "⏳", "color": "#fff4cc"},
            cls.FAILED: {"icon": "❌", "color": "#ff0000"},
            cls.CLOSED: {"icon": "🔒", "color": "#e6f7ff"},
            cls.SUCCESS: {"icon": "✔️", "color": "#fff1f0"},
            cls.HELD: {"icon": "✋", "color": "#fff1f0"},
        }.get(value, {"icon": "❓", "color": "#ffe6e6"})