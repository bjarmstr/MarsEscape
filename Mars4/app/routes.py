'''
Created on Jan. 29, 2021

@author: Jean Armstrong
'''
from app import app
from flask import render_template, request, flash, Response, session, redirect, url_for

from app import redis_client
from app.computations import op_data_from_db, error_codes_from_db,  isInteger, format_min_sec
import json
import time


#context process allows variable to be passed to all routes
@app.context_processor  
def context_processor():
    return dict (colonyName='Mars One')

@app.route('/')
@app.route('/index')
def index():
    return '<h1>MarsOne Running - /scenario for EscapeRoom Admin</h1>'

#**********User pages************
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    WAIT_TIME = (16)
    hint_list =["HINT:  the surface on Mars","HINT: What is the surface material on Mars called?",
                "HINT:  Look on the surface of Mars", "HINT: Look closely, the definition is inscribed here"]
    if request.method == 'POST':
        if  (request.form['password']).casefold() != "regolith":
            hint = int(session['hint'])
            error = 'Invalid Credentials. Please try again.'
            attempts= int(session['failed_attempts'])
            attempts += 1
            if attempts == 2:
                flash(hint_list[hint])
                session['hint_timer']= time.time()
                session['hint'] = 1
            if attempts > 2:
                elapsed_time = (time.time() - session['hint_timer'])
                if hint < 3:
                    if elapsed_time <= WAIT_TIME:
                        error = "Invalid Credentials. Hint available in {}.".format(format_min_sec(WAIT_TIME - elapsed_time))
                    else:
                        session['hint_timer']= time.time()
                        session['hint'] = hint+1
                    flash(hint_list[session['hint']])
                    if  hint > 1:
                            flash(hint_list[1])
                else:
                    flash(hint_list[3])
                    flash(hint_list[1])
            session['failed_attempts'] = attempts
          
        else:
            return redirect(url_for('index'))
    else:
        #GET request initialize variables
        session['failed_attempts'] = 0
        session['hint'] = 0
    return render_template('login.html', error=error)

#***********Admin pages *****************
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
    return Response(event_stream(), mimetype="text/event-stream")
 

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
        session['scenario_time']=scenario_time

    scenario_list = {'Fuse Blows': '5', 'Control board fails': '10', 'CO2 line leak': '15', 'D': '12'}
    return render_template('scenario.html', title='Scenarios', scenario_list=scenario_list,
                            is_checked = is_checked, base_time = base_time,  
                            error=error, scenario_time=scenario_time)


@app.route('/piping', methods=['GET', 'POST'])
def piping():
    error = None
        #is this the first time to this page and came from scenario?
    url = request.referrer
    if scenario in url:
        #start tank level calculation threads
        #reset_database
        
        #set initial time for countdown timer
        session['starttime']= time.time()
        if (int(session.get("scenario_time")) == 0):
            return redirect(url_for('scenario'))
        else:
            countdown = (session.get("scenario_time"))*60
                
    else:
    #account for time elapsed since countdown started
        elapsed_time = (time.time()) - (session.get('starttime'))
        countdown = (session.get("scenario_time"))*60 - elapsed_time  
        if request.method == 'POST':
            pipe_data = request.form
            for key, value in pipe_data.items():
                if value: #was a value entered in the field?
                    if not isInteger(value):
                        flash('correct your error and RESUBMIT')
                        error = " Threshold value must be an integer "
                    else:
                        print("threshold",key,value)
                        redis_client.hset("threshold",key,value)

    
    pipe_thresh = redis_client.hgetall("threshold")   
    return render_template('piping.html', title='Piping', countdown=countdown,
                           error=error, pipe_thresh =pipe_thresh )

        

@app.route('/operations', methods=['GET', 'POST'])
def operations():
    error_input = None
    if request.method == 'POST':
        op_data = request.form
        for key, value in op_data.items():
            #validate form data
            if value: #was a value entered in the field?
                print("value",value,type(value))
                if isInteger(value):   
                    if  "error" in key:
                        dict_value = {key:value}
                        redis_client.xadd(key,dict_value)
                    elif (100 < int(value) <150) and "level" in key:
                        flash('FIX Entry Error and RESUBMIT')
                        error_input = "Valid tanks level maximum is 100% "
                    elif (int(value) >150) or (int(value) <0):
                        flash('FIX Entry Error and RESUBMIT')
                        error_input = " Valid Assembly rates are between 0 & 150%" 
                    else:
                    #H2O example, {"H2O-level":"30"})
                        stream = (key.split('-'))[0]
                        dict_value = {key:value}
                        #print(dict_value,"value for stream")
                        #place valid data from form into database
                        redis_client.xadd(stream,dict_value)
                    
                else: 
                    flash('FIX Entry Error and RESUBMIT')
                    error_input = "All values must be an integer "

                    
                 
    error_code= error_codes_from_db()  
    print(error_code,"error code")              
    complete_values = op_data_from_db() #get all operations rates/levels from database           
    elapsed_time = (time.time()) - (session.get('starttime'))
    countdown = (session.get("scenario_time"))*60 - elapsed_time 
    return render_template('operations.html', title='Operations',
                           error_code=error_code, op_valid= complete_values, 
                           error = error_input, countdown=countdown)

