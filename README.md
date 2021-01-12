# Lexpert

Unfortunately, our application doesn’t have an interface because of time shortage. To create a database we just run the file named «import_manager.py» for every act we wanted to load.

**Preparatory steps before running import_manager.py:**
1. Request and save the json file in some folder and specify the path to this file in the line 18 of predict.py
2. Specify the trial time, so we could enable the Google application service account for this time to provide an access to our model and our endpoint. (We are sorry for this but we are being hacked so we can't have our service account enabled all the time).  
3. Open a regulation on «eur-lex» like this one https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A32013R0153
4. Press «Document information» button (like in the screenshot) and save as an html file ![file](https://user-images.githubusercontent.com/59837137/104319219-9fd01d80-54f1-11eb-85b9-0458169c3760.png)  
5. Specify the path to the html file in the line 486 of import_manager.py 
6. Make sure that predict.py and db.py are located together with import_manager.py so import_manager.py can call them
7. Run import_manager.py

**Description:**

import_manager.py calls the file «predict.py» to predict whether text comprises legal terms or other labels. predict.py calls the text entity extraction model deployed on the Google AI Platform. import_manager.py calls the file «db» for modeling database nodes and relationships into Python classes.
data_migration.py is a stand alone file used to transfer data from the local database to the database deployed in the cloud since the cloud database expires every 10 days.  
So originally import_manager.py writes data to the local db, but to alleviate testing we changed the path directly to the cloud database (line 83 import_manager.py)
 
If there will be any problems with running files, please contact Nataly.
Best regards, Hammurabi AI
