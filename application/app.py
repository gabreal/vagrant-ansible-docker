
from flask import Flask,render_template,g,abort
import os
import consul
from pg import DB


app = Flask(__name__, template_folder='')





class pgcon(object):
    def __init__(self):
        self.pgsql = {}
        self.result = None
        self.status = "Unknown"
        self.db = None

    def query_consul(self):
        '''
        at first try to get the consul coordinates from the environment. these 
        should be set by docker due to container linking. then fetch postgresql 
        container coordinates.
        '''

        try:
            g.consul_server = os.environ['CONSUL_PORT_8500_TCP_ADDR']
            g.consul_port = os.environ['CONSUL_PORT_8500_TCP_PORT']
        except:
            if app.debug:
                g.consul_server = '172.17.0.2'
                g.consul_port = '8500'
            else:
                raise EnvironmentError('No consul environment variables available')
    
        try:
            c = consul.Consul(host=g.consul_server, port=g.consul_port)
            cresponse = c.kv.get('postgresql', recurse = True)[1]
        except:
            raise LookupError('Error in connecting to the Consul server')

        try:
            for d in cresponse:
                v = d['Value']
                k = d['Key'].split('/')[-1]
                self.pgsql[k] = v
        except:
            raise AttributeError('Something is wrong with Consuls response')


    def connect(self):
        if not self.pgsql:
            raise ValueError('No coordinates to connect to the db.')
        try:
            self.db = DB(dbname = self.pgsql['user'], 
                         host = self.pgsql['host'],
                         port = int(self.pgsql['port']),
                         user = self.pgsql['user'],
                         passwd = self.pgsql['password'])
        except:
            raise IOError('Could not connect to the db.')
        self.status = "Connected"





    def query(self,  p = None ):
        '''
        connect to the db and retrieve something
        '''

        if not self.db:
            self.connect()

        if not self.db:
            self.result = { 'postgresql db: ': 'not connected' }
            return

        if p:
            self.result = self.db.query(p)


    def call(self, m):
        if not self.db:
            self.connect()
        self.result =  getattr(self.db, m)()


        
    def disconnect(self):
        try:
            self.db.close()
        except:
            pass





@app.before_request
def before_request():
    g.pgsql = pgcon()



@app.after_request
def after_request(response):
    g.pgsql.disconnect()
    return response



@app.route('/')
def hello_world():

    try:
        g.pgsql.query_consul()
        desc = "Connecting to Consul server at %s:%s" % (g.consul_server, g.consul_port)
    except Exception as e:
        desc = "No Connection to Consul server: %s" % e

    try:
        g.pgsql.call('get_tables')
        g.pgsql.query("create table fruits(id serial primary key, name varchar)")
        g.pgsql.call('get_tables')
        desc = "List of tables of db '%s' at server '%s': " % (g.pgsql.pgsql['user'], g.pgsql.pgsql['host'])
    except Exception as e:
        desc = "Something went wrong in connecting to the db: %s" % e

    name = "World"
    try:
        return render_template('index.html', desc=desc, name=name, table=g.pgsql.result, status=g.pgsql.status)
    except:
        return abort(500)


if __name__ == "__main__":
    app.run( host="0.0.0.0", debug=True)
