#!/usr/bin/env python3
import re, random
#random.seed(0)

# LEVEL_CONST is the maximum number of proxy servers in a level, so that
# we can look at a proxy and determine which level it is.
LEVEL_CONST = 100

Num_Origin = 10
My_Pages = 10

def max_level():
    """ The average number of hops for a request before reaching origin """
    return 10
def max_width():
    """ The average number of proxy servers at each level """
    return 10
def get_degree():
    """ The number of parent servers per proxy """
    return 2
def rand(i): return random.randint(0,i-1)
def unique(lst): return list(set(lst))

def proxy_name(lvl, rank): return lvl*LEVEL_CONST + rank

class Cache:
    def __init__(self, max_size=4):
        self._data = {}
        self._max_size = max_size
    def max_size(self): return self._max_size
    def store(self, key, value):
        self._data[key] = [0, value]
        self.age_keys
        self.prune
    def read(self, key):
        if key not in self._data: return None
        value = self._data[key]
        self.renew(key)
        self.age_keys()
        return value[1]
    def renew(self, key):
        self._data[key][0] = 0
    def delete_oldest(self):
        m = max(i[0] for i in self._data.value)
        self._data = {k:v for k,v in self._data.items() if v[0] == m}
    def age_keys(self):
        for k in self._data: self._data[k][0] += 1
    def prune(self):
        if len(self._data) > self._max_size: self.delete_oldest()

class Request:
    def __init__(self, url):
        self._url = url
        match = re.search('http:\/\/([a-z0-9:]+)\/(.*)$', url, re.IGNORECASE)
        if not match: raise Error('Not matched')
        self._domain = match.group(1)
        self._page = match.group(2)
    def domain(self): return self._domain
    def page(self): return self._page
    def header(self): return None
    def url(self): return self._url

class Response:
    def __init__(self, domain, url, content, header, status):
        self._page = {'domain': domain, 'url': url, 'content': content, 'header': header}
        self._status = status
        self._page['header']['Q'] = 0
    def __str__(self): return self._page['url']
    def set_reward(self, r): self._page['header']['QReward'] = str(r)
    def get_reward(self): return int(self._page['header']['QReward'])
    def get_q_header(self): return self._page['header']['Q']
    def set_q_header(self, value): self._page['header']['Q'] = value
    def status(self): return self._status

class HTTPServer:
    def domain(self): return self._domain
    def __init__(self, domain, pages):
        self._domain = domain
        self._page = {}
        for path in pages:
            self._page[path] = Response(domain,path,"< A page from #{domain}/#{p} >",{}, 200)
    def get(self, path): return self._page[path]

class Reward:
    def __init__(self, proxy): self._proxy = proxy
    def get_reward(self, status):
        # if we are not the end point, just return -1 * load
        # if we are, then return (100 - load)
        if status == 'MidWay': return -1 * self._proxy.load()
        if status == 'EndPoint': return 500
        if status == 'CacheHit': return 500
        if status == 'NoService': return -500
        assert False

class Q:
    def __init__(self, parents):
        self._q = {}
        self._parents = parents
    
    def get_q(self, s_url_domain,a_parent):
        key = self.to_key(s_url_domain,a_parent)
        if key not in self._q: self._q[key] = 0
        return self._q[key]
    def put_q(self, s_url_domain, a_parent, value):
        key = self.to_key(s_url_domain,a_parent)
        self._q[key] = value
    
    def max_a(self,s_url_domain):
        # best next server for this state.
        srv = self._parents[0]
        maxq = self.get_q(s_url_domain, srv)
        for a_p in self._parents:
           q = self.get_q(s_url_domain, a_p)
           if q > maxq:
               maxq = q
               srv = a_p
        return srv
    
    def to_key(self, s_url_domain, a_parent):
        return 'url[%s]: parent[%d]' % (s_url_domain,a_parent)

class Policy:
    def __init__(self, proxy, q):
        self._proxy = proxy;
    def next(self, req):
        global topology
        # greedy. Just return the first policy found.
        return topology[self._proxy.name()]['next'][0]
    def update(self, domain,proxy,last_max_q, reward):
        pass
    def max_a_val(self, domain): return 0

class QPolicy:
    def __init__(self, proxy,q):
        self._proxy = proxy
        self._alpha = 0.1
        self._beta = 1
        # our q value estimate may be based on
        # the load of the server
        # if the url is in the cache
        # or the cache hit ratio
        # RAM available
        # uptime

        # Action is the next server to choose from
        self._q = q
        self._t = 0
    def q(self): return self._q
    def next(self, req):
        global path
        global topology
        #GLIE
        self._t += 1
        s = rand(self._t) + 1
        if s == 1:
            len_ = len(topology[self._proxy.name()]['next'])
            s = rand(len_)
            path.append('*')
            return topology[self._proxy.name()]['next'][s]
        else:
            proxy = self._q.max_a(req.domain())
            return proxy

    def max_a_val(self, s_url_domain):
        a_parent = self._q.max_a(s_url_domain)
        val = self._q.get_q(s_url_domain, a_parent)
        return val
    def update(self, s_url_domain, a_parent, last_max_q, reward):
        # Q(a,s)  = (1-alpha)*Q(a,s) + alpha(R(s) + beta*max_a(Q(a_,s_)))
        # the a is self here.
        q_now = self._q.get_q(s_url_domain, a_parent)
        q_new = (1 - self._alpha) * q_now + self._alpha*(reward + self._beta*last_max_q)
        self._q.put_q(s_url_domain, a_parent, q_new)

# each proxy node maintains its own q(s,a) value
# each proxy is able to reach a fixed set of domains. for others, it has to
# rely on parents.
class ProxyNode:
    def __init__(self, name, domains, parents, kind, load):
        self._name = name
        self._kind = kind
        self._load = load
        self._parents = parents
        self._domains = domains
        self._q = Q(parents)
        self._policy = QPolicy(self, self._q)
        self._reward = Reward(self)
        self._cache = Cache()
    def policy(self): return self._policy
    def load(self):
        v = rand(2)
        if v == 0:
            self._load += 1
        else:
            self._load -= 1
        if self._load < 0 :
            self._load = 0
        return self._load
    def name(self): return self._name
    # use this proxy to send request.
    # it returns back a hashmap that contains the body of response
    # and a few headers.
    def request(self, req):
        global path, reward 
        # if the load is too high, decline the request.
        if self._load >= 100:
            # reset the load now because after denying the requests the load
            # should be lower.
            self._load = rand(100)+1
            res = Response(req.domain(),req.url(),'Can not service',
                    {'last_proxy': self._name}, 501)
            my_reward = self._reward.get_reward('NoService')
            res.set_reward(my_reward)
            reward.append(my_reward)
            return res
        s = self._cache.read(req.url())
        if s is not None:
            path.append(str(self._name))
            path.append("+")
            my_reward = self._reward.get_reward('CacheHit')
            s.set_reward(my_reward)
            reward.append(my_reward)
            return s
        res = self._request(req)
        if res.status() == 200:
            self._cache.store(req.url(),res)
        return res

    def _request(self, req):
        global path, reward 
        res = None
        path.append(str(self._name))
        for dom in self._domains:
           if int(req.domain()) == dom:
               res = self.fetch(req)
               my_reward = self._reward.get_reward('EndPoint')
               res.set_reward(my_reward)
               reward.append(my_reward)
               return res
        if self._name < LEVEL_CONST*2:
            res = Response(req.domain(),req.url(),'Can not service',
                    {'last_proxy':  self._name}, 501)
            my_reward = self._reward.get_reward('NoService')
            res.set_reward(my_reward)
            reward.append(my_reward)
            return res
        else:
            res = self.forward(req)
            my_reward = self._reward.get_reward('MidWay')
            res.set_reward(my_reward)
            reward.append(my_reward)
            return res
    
    def fetch(self, req):
        global server
        return server[int(req.domain())].get(req.page())

    def forward(self, req):
        #puts "req at #{self._name}"
        proxy = self._policy.next(req)
        res =  proxy_db(proxy).request(req)
        # updaate q
        last_max_q = int(res.get_q_header())
        
        reward = res.get_reward()
        self._policy.update(req.domain(),proxy,last_max_q, reward)
        
        # find the q value for the next best server for domain
        next_q = self._policy.max_a_val(req.domain())
        res.set_q_header(next_q)
        return res

topology = {}
proxydb = {}
def proxy_db(p):
    global proxydb
    # lookup and return proxy server.
    if p not in proxydb:
        kind = 'Proxy'
        if p < LEVEL_CONST*2:
            # we are an edge proxy. That is, servers
            # with ids 101, 102 etc. where the origins are
            # 1,2,...
            # We no longer have parents.
            domains = topology[p]['next']
            parents = []
            kind = 'Edge'
        else:
            domains = []
            parents = topology[p]['next']
        proxy = ProxyNode(p, domains, parents, kind, topology[p]['load'])
        proxydb[p] = proxy
    return proxydb[p]

class Network:
    def parents(self,p_id,lvl,rank,network_width):
        """
        Identify two random proxy servers in the level up as the parents for
        each proxy server.
        """
        num_parents = get_degree()
        direct_parent = p_id - LEVEL_CONST
        parent_proxies = [direct_parent]
        for i in range(1,num_parents+1):
            another_rank = (rank + rand(num_parents)) % network_width + 1
            another_id = another_rank + (lvl-1)*LEVEL_CONST
            parent_proxies.append(another_id)
        return unique(sorted(parent_proxies))

    def populate_origin_servers(self):
        # construct the origin servers
        server = {}
        for i in range(1,Num_Origin+1):
            pages = ["path-%d/page.html" % page for page in range(1,My_Pages+1)]
            server[i] = HTTPServer("domain%d.com" % i, pages)
        return server

    def populate_proxy_servers(self):
        # Links between proxies
        proxies = {}
        
        network_levels = max_level()
        network_width = max_width()
        
        for lvl in range(1,network_levels+1):
            for rank in range(1,network_width+1):
                p_id = proxy_name(lvl, rank)
                proxies[p_id] = self.parents(p_id,lvl,rank,network_width) 
        return self.init_loads(proxies)

    def __init__(self):
        # construct the initial topology
        global topology
        global server
        server = self.populate_origin_servers()
        #self._user_proxy = initial_proxies
        topology = self.populate_proxy_servers()

    def init_loads(self, proxies):
        network = {}
        parents = 0
        count = 0
        for p_id in proxies.keys():
            parents += len(proxies[p_id])
            count += 1
            network[p_id] = {'next': proxies[p_id], 'load': self.load()}
        print("==================================")
        print("degree = %d/%d = %f" % (parents, count, (parents * 1.0)/(count * 1.0)))
        return network
    def load(self):
        return rand(100)+1
    
    def user_req(self, req):
        #---------------------------------------
        # Modify here for first level proxy
        # get our first level proxy. Here it is 10X
        #---------------------------------------
        proxy = proxy_name(max_level(), rand(max_width()) + 1)
        #print("req starting at %s for %s" % (proxy, req.domain()))
        #print(req.url())
        res = proxy_db(proxy).request(req)
        return res
    def show_loads(self):
        for layer in range(1,5):
            for proxy in range(1, 5):
                n = layer*10 + proxy
                print(" " + str(n) + "(" + str(topology[n]['load'])+ ")")
            print()
    def show_max(self, domain):
        for layer in range(1, 5):
            l = layer*10
            for proxy in range(1, 5):
                p = proxy_db(proxy + l)
                x = p.policy.q.max_a(str(domain))
                print(" " + str(p.name()) + " (" + str(x) + ")")
            print()

path = []
reward = []
n = Network()
iter_total = 100
max_count = 0
for i in range(1,iter_total+1):
    count = 0
    total = 100
    for j in range(1,total+1):
        page = "path-%s/page.html" % (rand(10)+1)
        server_id = rand(10) + 1
        req = Request("http://" + str(server_id) + '/' + page)
        res = n.user_req(req)
        trejectory = ''.join([j + '>' for j in path]) + ("*" if res.status() == 200 else "X") + "  " + req.domain()
        #puts trejectory
        my_reward = ' '.join([str(j) for j in reward])
        total_reward = sum(reward)
        #puts "reward:(#{total_reward}) #{my_reward}"
        path = []
        reward = []
        if res.status() > 500: count += 1
    print("%d/%d" % (count,total))
    #puts "Loads:"
    #puts "---------------#{i}"
    max_count = i
    if count == 0: break
    #n.show_loads
    #(1..10).each do |i|
    #  puts "MaxAVal: " + i.to_s
    #  puts "---------------"
    #  n.show_max(i)
    #end
print("maxcount: ",max_count)

