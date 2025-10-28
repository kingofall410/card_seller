from django.db import models

class StatusBase(models.TextChoices):
    
    UNEXECUTED = "unexecuted", "Unexecuted"
    MANUAL = "manual", "Manual"
    AUTO = "auto", "Auto"
    LOCKED = "locked", "Locked"
    LISTED = "listed", "Listed"

    @classmethod
    def get_id(cls, value):
        return StatusBase.values.index(value)

    @classmethod
    def get_meta(cls, value):
        print(value)
        return {
            cls.UNEXECUTED: {"icon": "🚫", "color": "#ffffff"},
            cls.MANUAL: {"icon": "✋", "color": "#fffbe6"},
            cls.AUTO: {"icon": "🤖", "color": "#fff1f0"},
            cls.LOCKED: {"icon": "🔒", "color": "#f6ffed"},
            cls.LISTED: {"icon": "✔️", "color": "#e6f7ff"},
        }.get(value, {"icon": "❓", "color": "#ffffff"})
