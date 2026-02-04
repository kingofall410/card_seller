from django.db import models

class StatusBase(models.TextChoices):
    
    UNEXECUTED = "unexecuted", "Unexecuted"
    LISTED = "listed", "Listed"
    PENDING = "pending", "Pending"
    MANUAL = "manual", "Manual"
    AUTO = "auto", "Auto"
    LOCKED = "locked", "Locked"
    FAILED = "failed", "Failed"
    SUCCESS = "success", "Success"
    CLOSED = "closed", "Closed"

    @classmethod
    def get_id(cls, value):
        return StatusBase.values.index(value)

    @classmethod
    def get_meta(cls, value):
        #print(value)
        return {
            cls.UNEXECUTED: {"icon": "🚫", "color": "#ffffff"},
            cls.MANUAL: {"icon": "✋", "color": "#fffbe6"},
            cls.AUTO: {"icon": "🤖", "color": "#fff1f0"},
            cls.LOCKED: {"icon": "", "color": "#f6ffed"},
            cls.LISTED: {"icon": "✔️", "color": "#e0f7ff"},
            cls.PENDING: {"icon": "⏳", "color": "#fff4cc"},
            cls.FAILED: {"icon": "❌", "color": "#e6f7ff"},
            cls.CLOSED: {"icon": "🔒", "color": "#e6f7ff"},
            cls.SUCCESS: {"icon": "✔️", "color": "#e6f7ff"},
        }.get(value, {"icon": "❓", "color": "#ffe6e6"})