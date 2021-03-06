#!/usr/bin/env python3
import re, random
#random.seed(0)

Alpha = 0.1
Beta = 1

class Cache:
    def __init__(self, max_size=4): self._data, self._max_size = {}, max_size

    def __setitem__(self, key, value):
        self._data[key] = [0, value]
        self._age_keys()
        self._prune()

    def __getitem__(self, key):
        if key not in self._data: return None
        value = self._data[key]
        self._renew(key)
        self._age_keys()
        return value[1]

    def _renew(self, key): self._data[key][0] = 0

    def _delete_oldest(self):
        m = max(i[0] for i in self._data.values())
        self._data = {k:v for k,v in self._data.items() if v[0] == m}

    def _age_keys(self):
        for k in self._data: self._data[k][0] += 1

    def _prune(self):
        if len(self._data) > self._max_size: self._delete_oldest()

class HTTPRequest:
    def __init__(self, domain, page):
        self._domain, self._page = domain, page
        self._url = 'http://%s/%s' % (domain, page)
    def domain(self): return self._domain
    def page(self): return self._page
    def header(self): return None
    def url(self): return self._url

class HTTPResponse:
    def __init__(self, domain, url, content, header, status=200):
        self._page = {'domain': domain, 'url': url, 'content': content, 'header': header}
        self._status = status
        self._page['header']['Q'] = 0
    def __str__(self): return self._page['url']
    def set_reward_header(self, r): self._page['header']['QReward'] = str(r)
    def get_reward_header(self): return int(self._page['header']['QReward'])
    def get_q_header(self): return self._page['header']['Q']
    def set_q_header(self, value): self._page['header']['Q'] = value
    def status(self): return self._status

class HTTPServer:
    def domain(self): return self._domain
    def __init__(self, domain, paths):
        self._domain = domain
        self._pages = {path:HTTPResponse(domain,path,
            "< A page from %s/%s >" % (domain, path),{}) for path in paths}
    def get(self, path): return self._pages[path]

class Reward: MidWay, EndPoint, CacheHit, NoService = -1, 500, 500, -500

class Q:
    def __init__(self, parents): self.parents, self._q = parents, {}

    def __getitem__(self, val):
        key = self.to_key(val)
        if key not in self._q: self._q[key] = 0
        return self._q[key]

    def __setitem__(self, val, value): self._q[self.to_key(val)] = value

    def to_key(self, val): return 'domain[%s]: proxy[%d]' % val

    def explore(self): return random.choice(self.parents)

    def max_a(self,s_url_domain):
        # best next server for this state.
        srv = self.parents[0]
        maxq = self[(s_url_domain, srv)]
        for parent in self.parents:
           q = self[(s_url_domain, parent)]
           if q > maxq: maxq, srv = q, parent
        return srv

class QPolicy:
    def __init__(self, lst): self._q, self._time_step = Q(lst), 0

    def q(self): return self._q

    def next_hop(self, req):
        # GLIE - Greedy in the limit, with infinite exploration
        # slowly converge to pure greedy as time steps increase.
        # * If a state is visited infinitely often, then each action
        #   In that state is chosen infinitely often
        # * In the limit, the learning policy is greedy wrt the
        #   learned Q function with probability 1
        s = random.randint(0, self._time_step)
        self._time_step += 1
        if s == 0: return self._q.explore()
        else: return self._q.max_a(req.domain())

    def max_a_val(self, s_url_domain):
        a_parent = self._q.max_a(s_url_domain)
        return self._q[(s_url_domain, a_parent)]

    def update(self, s_url_domain, a_parent, last_max_q, reward):
        # Q(a,s)  = (1-alpha)*Q(a,s) + alpha(R(s) + beta*max_a(Q(a_,s_)))
        q_now = self._q[(s_url_domain, a_parent)]
        q_new = (1 - Alpha) * q_now + Alpha*(reward + Beta*last_max_q)
        self._q[(s_url_domain, a_parent)] = q_new

# each proxy node maintains its own q(s,a) value
# each proxy is able to reach a fixed set of domains. for others, it has to
# rely on parents.
class ProxyNode:
    def __init__(self, name, domains, parents):
        self._name, self._parents, self._domains = name, parents, domains
        self._policy = QPolicy(list(parents.keys()))
        self._reward = Reward()
        self._cache = Cache()

    # use this proxy to send request.
    # it returns back a hashmap that contains the body of response
    # and a few headers.
    def request(self, req):
        res = self._cache[req.url()]
        if res is not None:
            res.set_reward_header(self._reward.CacheHit)
            return res
        res = self._request(req)
        if res.status() == 200:
            self._cache[req.url()] = res
        return res

    def is_edge(self): return My_Network.is_edge(self._name)

    def knows_origin(self, domain): return domain in self._domains

    def fetch(self, req): return self._domains[req.domain()].get(req.page())

    def _request(self, req):
        # is this one of the domains we can serve?
        if self.knows_origin(req.domain()):
           res = self.fetch(req)
           res.set_reward_header(self._reward.EndPoint)
           return res
        elif self.is_edge():
            res = HTTPResponse(req.domain(),req.url(),
                    "Can't service", {'last_proxy':  self._name}, 501)
            res.set_reward_header(self._reward.NoService)
            return res
        else:
            res = self.forward(req)
            res.set_reward_header(self._reward.MidWay)
            return res

    def forward(self, req):
        proxy = self._policy.next_hop(req)
        res =  self._parents[proxy].request(req)
        # update q
        last_max_q = int(res.get_q_header())

        reward = res.get_reward_header()
        self._policy.update(req.domain(),proxy,last_max_q, reward)

        # find the q value for the next best server for domain
        next_q = self._policy.max_a_val(req.domain())
        res.set_q_header(next_q)
        return res


class Network:
    def __init__(self, lvl_const, num_origin, num_pages, num_parents, network_width, network_levels):
        # the maximum limit for network_width
        self._lvl_const = lvl_const
        # the numbeer of origin servers
        self._num_origin = num_origin
        # the number of pages per origin server
        self._num_pages = num_pages
        # The number of parent servers per proxy
        self._num_parents = num_parents
        # The average number of proxy servers at each level
        self.network_width = network_width
        # The average number of hops for a request before reaching origin
        self.network_levels = network_levels

        servers = self.populate_origin_servers()
        proxies = self.populate_proxy_servers() # keys are in insert order
        self._db = {}
        for p in proxies.keys(): self.create_proxy(p, proxies[p], servers)

    def proxy_name(self, lvl, rank): return lvl*self._lvl_const + rank
    # an edge proxy. That is, servers
    # with ids 101, 102 etc. where the origins are
    # 1,2,...
    def is_edge(self, i): return i <  self._lvl_const*2
    def parents(self,p_id,lvl,rank,network_width):
        """
        Identify two random proxy servers in the level up as the parents for
        each proxy server.
        """
        direct_parent = p_id - self._lvl_const
        parent_proxies = {direct_parent}
        for i in range(1,self._num_parents+1):
            another_rank = (rank + random.randint(0, self._num_parents-1)) % network_width + 1
            parent_proxies.add(self.proxy_name(lvl-1, another_rank))
        return list(parent_proxies)

    def populate_origin_servers(self):
        # construct the origin servers
        server = {}
        for i in range(1,self._num_origin+1):
            paths = ["path-%d/page.html" % page for page in range(1,self._num_pages+1)]
            server[i] = HTTPServer("domain%d.com" % i, paths)
        return server

    def populate_proxy_servers(self):
        proxies = {}
        for lvl in range(1,self.network_levels+1):
            for rank in range(1,self.network_width+1):
                p_id = self.proxy_name(lvl, rank)
                proxies[p_id] = self.parents(p_id,lvl,rank,self.network_width)
        return proxies

    def create_proxy(self, p, parents, servers):
        if p not in self._db:
            if self.is_edge(p):
                domains, parents = {p:servers[p] for p in parents}, {}
            else:
                domains, parents = {}, {p:self._db[p] for p in parents}
            proxy = ProxyNode(p, domains, parents)
            self._db[p] = proxy
        return self._db[p]

    def user_req(self, req):
        proxy = self.proxy_name(self.network_levels,
                random.randint(1, self.network_width))
        # print("req starting at %s for %s" % (proxy, req.domain()))
        # print(req.url())
        res = self._db[proxy].request(req)
        return res

# Level_Const is the maximum number of proxy servers in a level, so that
# we can look at a proxy and determine which level it is.
Level_Const, Num_Origin, Num_Pages, Num_Parents, Network_Width, Network_Levels = 100, 10, 10, 2, 10, 10
My_Network = Network(Level_Const, Num_Origin, Num_Pages, Num_Parents, Network_Width, Network_Levels)
iter_total, total = 100, 100
max_count = 0
for i in range(iter_total):
    count = 0
    for j in range(total):
        page = "path-%s/page.html" % (random.randint(1,10))
        server_id = random.randint(1,10)
        req = HTTPRequest(server_id, page)
        res = My_Network.user_req(req)
        if res.status() > 500: count += 1
    print("%d/%d" % (count,total))
    max_count = i
    if count == 0: break
print("maxcount: ",max_count)

