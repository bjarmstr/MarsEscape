'''
Created on Jan. 29, 2021

@author: Jean Armstrong
'''
from app import app
from flask import render_template, request, flash, Response, session, redirect, url_for

from app import redis_client
from app.computations import scenario_list, isInteger
import json
import time


#context process allows variable to be passed to all routes
@app.context_processor  
def context_processor():
    return dict (colonyName='Mars One')

@app.route('/redisbox')
def redisbox():
    myvar = redis_client.get('potato')
    print(myvar)
    #myvar2 = scenario_list('test')
    #print (myvar2, "myvar2")
    return render_template('redisbox.html', title='Redisbox', myvar=myvar)

@app.route('/stream')
def stream():  
    def event_stream():
        while True:
            stream_data = redis_client.xread({'OGA': '$', 'SRA':'$', 'WPA':'$', 
                                              'CDRA':'$', 'H2O':'$', 'CO2':'$'}, block=0, count=10)
            #parse data, presently not passing along stream name and time id stamp
            
            print(stream_data, "rawdata from stream ",type(stream_data))
            raw_data = stream_data[0][1]
            dict_data = raw_data[0][1]
            for (equip_parm,value) in dict_data.items(): 
                fdata ={equip_parm:value}
                fj = json.dumps(fdata)
                print(fj,"json",type(fj))
            yield 'data: %s\n\n' % fj 
    return Response(event_stream(),
                          mimetype="text/event-stream")
 

@app.route('/scenario', methods=['GET', 'POST']) #piping clock only starts if previous page was /scenario
def scenario():
    error = None
    scenario_time = 0
    if request.method == 'POST':
        
        base_time = request.form['base-time']  
        if not isInteger(base_time):
            flash('CORRECT Entry Error and RESUBMIT')
            error = " Base time must be an integer "
        is_checked = request.form 
        if error is None:
            for key, value in is_checked.items():
                scenario_time += int(is_checked[key])        
        session['scenario_time']=scenario_time 
    
    else:
        is_checked = ""
        base_time = 30
        scenario_time=30
        session['starttime']= ""

    scenario_list = {'Fuse Blows': '5', 'Control board fails': '10', 'CO2 line leak': '15', 'D': '12'}
    return render_template('scenario.html', title='Scenarios', scenario_list=scenario_list,
                            is_checked = is_checked, base_time = base_time,  
                            error=error, scenario_time=scenario_time)


@app.route('/piping')
def piping():
    url = request.referrer
    if (url == "http://127.0.0.1:5000/scenario"):
        session['starttime']= time.time()
        if (int(session.get("scenario_time")) == 0):
            return redirect(url_for('scenario'))
        else:
            countdown = (session.get("scenario_time"))*60
    else:
        elapsed_time = (time.time()) - (session.get('starttime'))
        countdown = (session.get("scenario_time"))*60 - elapsed_time     
    return render_template('piping.html', title='Piping', countdown=countdown)

        

@app.route('/operations', methods=['GET', 'POST'])
def operations():
    error = None
    if request.method == 'POST':
        #SRA_override= request.form['SRA_rate']
        op_data = request.form
        for key, value in op_data.items():
                if value: #was a value entered in the field?
                    if not isInteger(value):
                        flash('FIX Entry Error and RESUBMIT')
                        error = "All values must be an integer "
                    else:
                        to_stream= key
                print (key,":",value)
      
    else:
        op_data = ""  #need initial value from database
    elapsed_time = (time.time()) - (session.get('starttime'))
    countdown = (session.get("scenario_time"))*60 - elapsed_time 
    return render_template('operations.html', title='Operations',
                           error=error, op_data=op_data, countdown=countdown)

