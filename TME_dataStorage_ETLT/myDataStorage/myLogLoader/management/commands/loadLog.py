from django.core.management.base import BaseCommand, CommandError
from myLogLoader.models import ProduitLog
from myLogLoader.serializers import ProduitLogSerializer
from myLogLoader.config import baseUrl
import requests
import time

class Command(BaseCommand):
    help = 'Refresh the list of logs from last logID.'

    def add_arguments(self, parser):
        parser.add_argument('lastLogID',type=int)

    def handle(self, *args, **options):
        currentLogID = options['lastLogID']
        self.stdout.write('['+time.ctime()+'] Refreshing data from logID '+str(currentLogID)+'...')
### PARTIE A ADAPTER ###
        ProduitLog.objects.all().delete()
### PARTIE A ADAPTER ###
        while True:
            response = requests.get(baseUrl+'logProduits/'+str(currentLogID)+'/')
            jsondata = response.json()
            try:
                serializer = ProduitLogSerializer(data={
                                                        'dateID':jsondata['dateID'],
                                                        'prodID':jsondata['prodID'],
                                                        'catID':jsondata['catID'],
                                                        'fabID':jsondata['fabID'],
                                                        })
                if serializer.is_valid():
                    serializer.save()
                    self.stdout.write(self.style.SUCCESS('['+time.ctime()+'] Successfully added log id="%s"' % jsondata['logID']))
                    currentLogID+=1
                else:
                    break
            except KeyError as error:
                break
        self.stdout.write('['+time.ctime()+'] Data refresh terminated.')
