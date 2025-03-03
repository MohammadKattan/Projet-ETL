from django.db import models

# Create your models here.
class ProduitLog(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    dateID = models.IntegerField(default='-1')
    prodID = models.IntegerField(default='-1')
    catID = models.IntegerField(default='-1')
    fabID = models.IntegerField(default='-1')

    class Meta:
        ordering = ('prodID',)

