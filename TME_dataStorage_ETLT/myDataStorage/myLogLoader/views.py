import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from myLogLoader.config import baseUrl
from myLogLoader.models import ProduitLog
from myLogLoader.serializers import ProduitLogSerializer
from django.http import Http404
from django.http import JsonResponse
from django.http import HttpResponse

import os
from django.conf import settings

# Create your views here.
class ArchiveDeProduits(APIView):
    def get(self, request, format=None):
#        response = requests.get(baseUrl+str(1664))
#        jsondata = response.json()
#        return Response(jsondata)
        file_name = 'produits-tous'
        dir_path = os.path.join(os.path.join(settings.MEDIA_ROOT, 'myLogLoader/'), 'archive/')
        file_path = os.path.join(dir_path,file_name)
        try:
            with open(file_path, 'w') as outFile:
                for prodLog in ProduitLog.objects.all():
                    serializer = ProduitLogSerializer(prodLog)
                    jsondata = serializer.data
                    outFile.write(
                                  str(jsondata['dateID'])+" "+
                                  str(jsondata['prodID'])+" "+
                                  str(jsondata['catID'])+" "+
                                  str(jsondata['fabID'])+"\n"
                                 )
        except OSError as error:
            raise Http404
        if os.path.exists(file_path):
            with open(file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type="application/octet-stream")
                fh.close()
                response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(file_path)
                return response
        raise Http404

#
#class PromoList(APIView):
#    def get(self, request, format=None):
#        res=[]
#        for prod in ProduitEnPromotion.objects.all():
#            serializer = ProduitEnPromotionSerializer(prod)
#            response = requests.get(baseUrl+'product/'+str(serializer.data['tigID'])+'/')
#            jsondata = response.json()
#            res.append(jsondata)
#        return JsonResponse(res, safe=False)
##    def post(self, request, format=None):
##        NO DEFITION of post --> server will return "405 NOT ALLOWED"
#
#class PromoDetail(APIView):
#    def get_object(self, pk):
#        try:
#            return ProduitEnPromotion.objects.get(pk=pk)
#        except ProduitEnPromotion.DoesNotExist:
#            raise Http404
#
#    def get(self, request, pk, format=None):
#        prod = self.get_object(pk)
#        serializer = ProduitEnPromotionSerializer(prod)
#        response = requests.get(baseUrl+'product/'+str(serializer.data['tigID'])+'/')
#        jsondata = response.json()
#        return Response(jsondata)
##    def put(self, request, pk, format=None):
##        NO DEFITION of put --> server will return "405 NOT ALLOWED"
##    def delete(self, request, pk, format=None):
##        NO DEFITION of delete --> server will return "405 NOT ALLOWED"
