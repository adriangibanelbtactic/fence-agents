#!/usr/bin/env python

# Copyright (c) 2013, OVH SAS.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#* Redistributions of source code must retain the above copyright
#  notice, this list of conditions and the following disclaimer.
#* Redistributions in binary form must reproduce the above copyright
#  notice, this list of conditions and the following disclaimer in the
#  documentation and/or other materials provided with the distribution.
#* Neither the name of OVH SAS nor the
#  names of its contributors may be used to endorse or promote products
#  derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY OVH SAS AND CONTRIBUTORS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL OVH SAS AND CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
This module provides a simple python wrapper over the OVH REST API.
It handles requesting credential, signing queries...
"""

import requests
import hashlib
import time
import json

OVH_API_EU = "https://api.ovh.com/1.0"          # Root URL of OVH european API
OVH_API_CA = "https://ca.api.ovh.com/1.0"       # Root URL of OVH canadian API

class Api:
    """
    Simple wrapper class for OVH REST API.
    """
    
    def __init__ (self, root, applicationKey, applicationSecret, consumerKey = ""):
        """
        Construct a new wrapper instance.
        Arguments:
        - root: the ovh cluster you want to call (OvhApi.OVH_API_EU or OvhApi.OVH_API_CA)
        - applicationKey: your application key given by OVH on application registration
        - applicationSecret: your application secret given by OVH on application registration
        - consumerKey: the consumer key you want to use, if any, given after a credential request
        """
        self.baseUrl = root
        self.applicationKey = applicationKey
        self.applicationSecret = applicationSecret
        self.consumerKey = consumerKey
        self._timeDelta = None
        self._root = None
        
    def timeDelta (self):
        """
        Get the delta between this computer and the OVH cluster to sign further queries
        """
        if self._timeDelta is None:
            self._timeDelta = 0
            serverTime = int(requests.get(self.baseUrl + "/auth/time").text)
            self._timeDelta = serverTime - int(time.time())
        return self._timeDelta
    
    def requestCredential(self, accessRules, redirectUrl = None):
        """
        Request a Consumer Key to the API. That key will need to be validated with the link returned in the answer.
        Arguments:
        - accessRules: list of dictionaries listing the accesses your application will need. Each dictionary must contain two keys : method, of the four HTTP methods, and path, the path you will need access for, with * as a wildcard
        - redirectUrl: url where you want the user to be redirected to after he successfully validates the consumer key
        """
        targetUrl = self.baseUrl + "/auth/credential"
        params = {"accessRules": accessRules}
        params["redirection"] = redirectUrl
        queryData = json.dumps(params)
        q = requests.post(targetUrl, headers={"X-Ovh-Application": self.applicationKey, "Content-type": "application/json"}, data=queryData)
        return json.loads(q.text)
    
    def rawCall (self, method, path, content = None):
        """
        This is the main method of this wrapper. It will sign a given query and return its result.
        Arguments:
        - method: the HTTP method of the request (get/post/put/delete)
        - path: the url you want to request
        - content: the object you want to send in your request (will be automatically serialized to JSON)
        """
        targetUrl = self.baseUrl + path
        now = str(int(time.time()) + self.timeDelta())
        body = ""
        if content is not None:
            body = json.dumps(content)
        s1 = hashlib.sha1()
        s1.update("+".join([self.applicationSecret, self.consumerKey, method.upper(), targetUrl, body, now]))
        sig = "$1$" + s1.hexdigest()
        queryHeaders = {"X-Ovh-Application": self.applicationKey, "X-Ovh-Timestamp": now, "X-Ovh-Consumer": self.consumerKey, "X-Ovh-Signature": sig, "Content-type": "application/json"}
        if self.consumerKey == "":
            queryHeaders = {"X-Ovh-Application": self.applicationKey, "X-Ovh-Timestamp": now, "Content-type": "application/json"}
        req = getattr(requests, method.lower())
        # For debug : print "%s %s" % (method.upper(), targetUrl)
        result = req(targetUrl, headers=queryHeaders, data=body).text
        return json.loads(result)
    
    def get (self, path):
        """
        Helper method that wrap a call to rawCall("get")
        """
        return self.rawCall("get", path)
    
    def put (self, path, content):
        """
        Helper method that wrap a call to rawCall("put")
        """
        return self.rawCall("put", path, content)
    
    def post (self, path, content):
        """
        Helper method that wrap a call to rawCall("post")
        """
        return self.rawCall("post", path, content)
    
    def delete (self, path, content = None):
        """
        Helper method that wrap a call to rawCall("delete")
        """
        return self.rawCall("delete", path, content)
