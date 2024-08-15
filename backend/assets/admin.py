from django.contrib import admin
from .models import Appraiser, Asset, AssetMedia #, WareHouse

admin.site.register(Appraiser)
admin.site.register(Asset)
admin.site.register(AssetMedia)
# admin.site.register(WareHouse)