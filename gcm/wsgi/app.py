#!/usr/bin/python
from flask import Flask, request
from gcm import gcm
import simplejson
from db import mongo_datastore

app = Flask(__name__)

GCM_LIMIT = 1000

@app.route('/')
def handle_root():
    return 'gcm is running'

@app.route('/gcm/app/')
def handle_app_register():
    '''
    register app_id and app api key to datastore.

    received http get parameters:
    @param app_id: a string identifier for the api key
    @param api_key: api key obtained from google api console
    '''
    app_id = request.args.get('app_id', None)
    api_key = request.args.get('api_key', None)

    # check required parameters
    if app_id is None or api_key is None:
        return 'missing required arguments'

    db = mongo_datastore.get_db()
    # find existing
    q = {
        'app_id':app_id,
        }
    saved = db.apps.find_one(q)
    if saved is None:
        db_entry = {
            'app_id':app_id,
            'api_key':api_key,
        }
        db.apps.save(db_entry)
        return 'register api key %s for app %s' % (api_key, app_id)
    else:
        saved['api_key']=api_key
        db.apps.save(saved)
        return 'updated api key %s for app %s' % (api_key, app_id)

@app.route('/gcm/device/register/')
def handle_device_register():
    '''
    register device to database.
    '''
    app_id = request.args.get('app_id', None)
    reg_id = request.args.get('reg_id', None)

    if app_id is None or reg_id is None:
        return 'missing required arguments'

    db = mongo_datastore.get_db()
    if not check_app_id(db, app_id):
        return 'app_id doesn\'t exist'

    q = {
        'app_id':app_id,
        'reg_id':reg_id,
        }
    saved = db.devices.find_one(q)
    if saved is None:
        db_entry = {
            'app_id':app_id,
            'reg_id':reg_id,
        }
        db.devices.save(db_entry)
    return 'registered device %s for app %s' % (reg_id, app_id)


@app.route('/gcm/device/unregister/')
def handle_device_unregister():
    '''
    unregister device to database
    '''
    app_id = request.args.get('app_id', None)
    reg_id = request.args.get('reg_id', None)

    if app_id is None or reg_id is None:
        return 'missing required arguments'

    db = mongo_datastore.get_db()
    if not check_app_id(db, app_id):
        return 'app_id doesn\'t exist'

    q = {
        'app_id':app_id,
        'reg_id':reg_id,
        }
    db.devices.remove(q)
    return 'unregistered device %s for app %s' % (reg_id, app_id)

@app.route('/gcm/device/update/')
def handle_device_update():
    '''
    update device reg_id to database
    '''
    app_id = request.args.get('app_id', None)
    reg_id = request.args.get('reg_id', None)
    new_reg_id = request.args.get('new_reg_id', None)

    if app_id is None or reg_id is None or new_reg_id is None:
        return 'missing required arguments'

    db = mongo_datastore.get_db()
    if not check_app_id(db, app_id):
        return 'app_id doesn\'t exist'

    q = {
        'app_id':app_id,
        'reg_id':reg_id,
        }
    saved = db.devices.find_one(q)
    if saved is not None:
        saved['reg_id'] = new_reg_id
        db.devices.save(db_entry)
    return 'updated device %s for app %s' % (reg_id, app_id)


@app.route('/gcm/send/', methods=['POST'])
def handle_send_message():
    '''
    send gcm message.

    url parameters
    @param app_id: app id used to retrieve api key

    post body:application/json
    required key:
    data: message body to be delievered
    optional keys:
    reg_id_list: specify a list of device to be the receivers.
    if ommited, all registered devices of the app id will become receivers.
    '''
    app_id = request.args.get('app_id', None)
    data = None
    reg_id_list = None
    if len(request.data) == 0:
        return 'missing parameters'

    json = simplejson.loads(request.data)
    if 'data' not in json:
        return 'missing parameter - data'
    else:
        data = json['data']
    if 'reg_id_list' in json:
        reg_id_list = json['reg_id_list']

    db = mongo_datastore.get_db()

    q = {'app_id':app_id}
    app = db.apps.find_one(q)
    if app is None:
        return 'app_id doesn\'t exist'

    if reg_id_list is None:
        # find all devices for the app_id
        count = 0
        reg_id_list = []
        for device in db.devices.find(q):
            reg_id_list.append(device['reg_id'])
            if len(reg_id_list) == GCM_LIMIT:
                do_send_gcm_message(app['api_key'], reg_id_list, data)
                reg_id_list = []
                count += GCM_LIMIT
        do_send_gcm_message(app['api_key'], reg_id_list, data)
        count += len(reg_id_list)
        return 'sent to %d devices' % count
    else:
        # send to provided list
        total = len(reg_id_list)
        start = 0
        while start < total:
            end = start + GCM_LIMIT
            do_send_gcm_message(app['api_key'], reg_id_list[start:end], data)
            start = end + 1
        return 'sent to %d devices' % total

def do_send_gcm_message(api_key, reg_id_list, data):
    '''
    do send gcm message and handle errors to remove invalid devices
    '''
    if api_key is None or reg_id_list is None or data is None or len(reg_id_list) == 0:
        return 'missing arguments in do_send_gcm_message()'

    response= send_gcm_message(api_key, reg_id_list, data)

    db = mongo_datastore.get_db()
    ''' handle error '''
    if 'errors' in response:
        # handle errors
        errors = response['errors']

        for error, reg_id_list in errors.items():
            # remove invalid reg ids
            where = []
            for reg_id in reg_id_list:
                where.append({'reg_id':reg_id})
            q ={'$or':where}
            db.devices.remove(q)

    # TODO handle canonical to update devices
    #if 'canonical' in response:
    #    # handle errors
    #    errors = response['canonical']

    #    for error, reg_id_list in errors.items():
    #        # remove invalid reg ids
    #        for reg_id in reg_id_list:
    #            where.append({'reg_id':reg_id})
    #            q ={'$or':where}
    #            db.devices.save(q)
    return 'done'

def check_app_id(db, app_id):
    ''' check the app_id has existed '''
    # check app_id existed
    q = {'app_id':app_id}
    return has_collection_record(db.apps, q)

def has_collection_record(collection, q):
    saved = collection.find_one(q)
    return saved is not None

def send_gcm_message(api_key, reg_id_list, data):
    '''
    contact google GCM server to send message

    @param api_key: secret api key obtained from google api console
    @param reg_id_list: list of reg_id obtained by device after registering
    GCM
    @param data: content to be delivered to devices
    '''
    if api_key is None or len(reg_id_list)==0:
        return

    g = gcm.GCM(api_key)
    data = {"data": data, "from":"gcm-openshift"}
    try:
        response = g.json_request(registration_ids=reg_id_list, data=data)
        return response
    except Exception as e:
        return e.strerror

if __name__ == '__main__':
    app.run(debug=True)
