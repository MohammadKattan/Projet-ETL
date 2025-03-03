from rest_framework.serializers import ModelSerializer
from myLogLoader.models import ProduitLog

class ProduitLogSerializer(ModelSerializer):
    class Meta:
        model = ProduitLog
        fields = ('dateID','prodID','catID','fabID')
