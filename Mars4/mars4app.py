'''
Created on Jan. 29, 2021

@author: Jean Armstrong
'''
from app import app

#added below commands so flask will start with eclipse run button
if __name__ == '__main__': #here i assume you have put this code in a file that    
   app.run(debug=True, host='0.0.0.0')   #contains variable "app", which contains the instance of #Flask(__main__)
   