from django.db import models

class AssetAppraisalStatus(models.TextChoices):
    NOT_APPRAISED = 'not_appraised', 'Not Appraised'
    APPRAISAL_SUCCESSFUL = 'appraisal_successful', 'Appraisal Successful'
    APPRAISAL_FAILED = 'appraisal_failed', 'Appraisal Failed'

class AssetStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_AUCTION = 'in_auction', 'In Auction'
    SOLD = 'sold', 'Sold'

class AppraiserStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'

class AssetMediaType(models.TextChoices):
    IMAGE = "image", "Image"
    VIDEO = "video", "Video"
    DOCUMENT = "document", "Document"