'''
Created on Jan. 29, 2021

@author: Jean Armstrong
'''
from app import app
from flask import render_template, request, flash
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
    myvar2 = scenario_list('test')
    print (myvar2, "myvar2")
    return render_template('redisbox.html', title='Redisbox')

@app.route('/')
@app.route('/scenario')
@app.route('/index', methods=['GET', 'POST'])
def scenario():
    error = None
    if request.method == 'POST':
        checkOn = request.form 
        base_time = request.form['base-time']  
        if not isInteger(base_time):
            error = " Base time must be an integer "
            clock = 30
        else:
            clock =int(base_time)       
        
    else:
        checkOn = ""
        base_time = 30
        clock = 30
    scenario_list = [{'Fuse Blows': '5', 'Control board fails': '10', 'CO2 line leak': '15', 'D': '12'}]
    return render_template('scenario.html', title='Scenarios', scenario_list=scenario_list, checkOn = checkOn, base_time = base_time, clock=clock, error=error)


@app.route('/piping')
def piping():
    return render_template('piping.html', title='Piping')

@app.route('/operations', methods=['GET', 'POST'])
def operations():
    if request.method == 'POST':
        SRA_override= request.form['SRA_rate']
        CDRA_override=request.form['CDRA_rate']
        f = request.form
        for key in f.keys():
            for value in f.getlist(key):
                print (key,":",value)
    else:
        SRA_override = "number?"
        CDRA_override = "need initial value?"
        
    return render_template('operations.html', title='Operations' , SRA_override=SRA_override, CDRA_override=CDRA_override)