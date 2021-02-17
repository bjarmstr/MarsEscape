'''
Created on Jan. 29, 2021

@author: Jean Armstrong
'''
from app import app
from flask import render_template, request, flash, Response
from app import redis_client
from app.computations import scenario_list, isInteger


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
            new_stream_data = redis_client.xread({'chat': '$', 'chat2':'$'}, block=0, count=10)
            yield 'data: %s\n\n' % new_stream_data   
    return Response(event_stream(),
                          mimetype="text/event-stream")
 
@app.route('/')
@app.route('/scenario')
@app.route('/index', methods=['GET', 'POST'])
def scenario():
    error = None
    if request.method == 'POST':
        checkOn = request.form 
        base_time = request.form['base-time']  
        if not isInteger(base_time):
            flash('CORRECT Entry Error and RESUBMIT')
            error = " Base time must be an integer "
            clock = 30
        else:
            clock =int(base_time)       
        
    else:
        checkOn = ""
        base_time = 30
        clock = 30
    scenario_list = {'Fuse Blows': '5', 'Control board fails': '10', 'CO2 line leak': '15', 'D': '12'}
    return render_template('scenario.html', title='Scenarios', scenario_list=scenario_list, checkOn = checkOn, base_time = base_time, clock=clock, error=error)


@app.route('/piping')
def piping():
    return render_template('piping.html', title='Piping')

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
                        to_database= key
                print (key,":",value)
      
    else:
        op_data = ""  #need initial value from database

        
    return render_template('operations.html', title='Operations',
                           error=error, op_data=op_data)

