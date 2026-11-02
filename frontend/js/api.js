/* Talks to the FastAPI backend. Every request carries the login token. */
(function () {
  "use strict";
  let token = null;
  try { token = localStorage.getItem("stayzen_token"); } catch (e) { /* storage blocked */ }

  async function call(method, url, body) {
    const opts = { method, headers: {} };
    if (token) opts.headers.Authorization = "Bearer " + token;
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    let res;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      throw new Error("Can't reach the StayZen server. Is it running? (py -m uvicorn main:app --reload)");
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (!res.ok) {
      let msg = data && data.detail ? data.detail : "Something went wrong (" + res.status + ").";
      if (Array.isArray(msg)) msg = msg.map(d => (d.loc ? d.loc[d.loc.length - 1] + ": " : "") + d.msg).join(", ");
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  window.API = {
    get: url => call("GET", url),
    post: (url, body) => call("POST", url, body === undefined ? {} : body),
    put: (url, body) => call("PUT", url, body),
    del: url => call("DELETE", url),
    setToken(t) {
      token = t;
      try { t ? localStorage.setItem("stayzen_token", t) : localStorage.removeItem("stayzen_token"); } catch (e) { /* ignore */ }
    },
    hasToken: () => !!token,
  };
})();
