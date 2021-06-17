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
            print("print working")
          
        else:
            answers= None
            session['answers'] = answers
            print(session.get("scenario_time"),"scen",session.get("starttime"),"start")
            session['starttime']=float(redis_client.get("starttime"))
            session['scenario_time']=int(redis_client.get('scenariotime'))
            print(session.get("scenario_time"),"scen",session.get("starttime"),"start")
            ##convert startime to timevalue
            
            return redirect(url_for('overview'))
    else:
        #GET request initialize variables
        session['failed_attempts'] = 0
        session['hint'] = 0   
    
    return render_template('login.html', error=error)

@app.route('/')
@app.route('/overview')
def overview():
    complete_values = op_data_from_db() #get all operations rates/levels from database           
    elapsed_time = (time.time()) - (session.get('starttime'))
    countdown = (session.get("scenario_time"))*60 - elapsed_time 
    return render_template('overview.html', title='Colonist',
                           op_valid= complete_values, countdown=countdown)

@app.route('/training')
def training():
    url = request.referrer
    session['toggle']= False
    if "quiz" in url:
        answer = "hilite_answer"
    else:
        answer = "none"
    elapsed_time = (time.time()) - (session.get('starttime'))
    countdown = (session.get("scenario_time"))*60 - elapsed_time 
    return render_template('training.html', answer = answer, countdown=countdown)


@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    answers = session.get('answers', None)
    print("answers",answers)
    correct = {"q1":"", "q2":"", "q3":""}
    
    if request.method == 'POST':
        count = 0
        correct = {"q1":"No", "q2":"No", "q3":"No"}
        answers = request.form
        if (len(answers)) == 3:
            if answers["q1"]=="q1b": 
                correct["q1"]="True"
                count += 1
            if answers["q2"]=="q2d": 
                correct["q2"]="True"
                count += 1
            if answers["q3"]=="q3b": 
                correct["q3"]="True"
                count +=1
        print(count)
        if count == 3:
            print("training complete")
            redis_client.set("trained","True")
            elapsed_time = (time.time()) - (session.get('starttime'))
            countdown = (session.get("scenario_time"))*60 - elapsed_time 
            return render_template ('trained.html', countdown=countdown)
        session['answers'] = answers
    page_toggle = session.get('toggle')  
    session['toggle']= True
    if page_toggle == False:
        btn_label = "submit"
    else: btn_label = "Re-review Training Material"   
    elapsed_time = (time.time()) - (session.get('starttime'))
    countdown = (session.get("scenario_time"))*60 - elapsed_time 
    return render_template('quiz.html', answers=answers, correct=correct,
                           page_toggle=page_toggle, btn_label=btn_label,
                           countdown=countdown)

@app.route('/circuit')
def circuit():
    return render_template('circuit.html')

@app.route('/errorcodes')
def errorcodes():
    return render_template('errorcodes.html')

@app.route('/flowdiagram')
def flowdiagram():
    return render_template('flowdiagram.html')

@app.route('/startup')
def startup():
    return render_template('startup.html')

@app.route('/tanklevels')
def tanklevels():         
    complete_values = op_data_from_db() #get all operations rates/levels from database           
    elapsed_time = (time.time()) - (session.get('starttime'))
    countdown = (session.get("scenario_time"))*60 - elapsed_time 
    return render_template('tanklevels.html', title='tanklevels', op_valid= complete_values, 
                          countdown=countdown)



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
    scenario_list = {'Fuse': '5', 'Circuit': '10', 'CO2leak': '5', 'Quiz': '5'}
    
    if request.method == 'POST':
        base_time = request.form['base-time']  
        if not isInteger(base_time):
            flash('CORRECT Entry Error and RESUBMIT')
            error = " Base time must be an integer "
        is_checked = request.form 
        if error is None:
            #scenarios default to NO
            for key in scenario_list:
                redis_client.hset("scenarios",key,"NO")
            #scenarios checked set to YES
            for key, value in is_checked.items():
                redis_client.hset("scenarios", key,key)
                scenario_time += int(is_checked[key])        
        session['scenario_time']=scenario_time 
    
    else:
        is_checked = ""
        base_time = 40
        scenario_time=40
        session['scenario_time']=scenario_time
        

    
    return render_template('scenario.html', title='Scenarios', scenario_list=scenario_list,
                            is_checked = is_checked, base_time = base_time,  
                            error=error, scenario_time=scenario_time)


@app.route('/piping', methods=['GET', 'POST'])
def piping():
    error = None
        #is this the first time to this page and came from scenario?
    url = request.referrer
    if "scenario" in url:
        #set initial time for countdown timer
        session['starttime']= time.time()
        #place times into redis for retrival by a different browser
        redis_client.set("starttime",time.time())
        redis_client.set("scenariotime",session.get("scenario_time"))
        
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
                if "trained" in key:
                    redis_client.set(key,value)
                elif isInteger(value): 
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

