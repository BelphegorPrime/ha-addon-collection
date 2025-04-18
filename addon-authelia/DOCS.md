# addon-authelia

Authelia - Home Assistant Community Add-ons

# Authelia Home Assistant add-on repository

Add-on documentation: <https://github.com/BelphegorPrime/addon-authelia/tree/master/addon-authelia/DOCS.md>

# Prerequisites

- You need a domain.
- `auth.example.com` should point the authelia instance and be secured with a valid SSL-certificate. (I would recommend [Nginx Proxy Manager](https://github.com/hassio-addons/addon-nginx-proxy-manager) to handle the certificate rollovers)

# IMPORTANT

If you use the [Nginx Proxy Manager](https://github.com/hassio-addons/addon-nginx-proxy-manager) you can follow this [this](https://www.authelia.com/integration/proxies/nginx-proxy-manager/) but the good thing is that this Addon provides the snippets for your domain too.
You can find the snippets in the `/share/nginx_snippets` directory. Please copy them inside your Nginx Proxy Manager Addon.

```bash
$ mkdir -p /addon_configs/a0d7b954_nginxproxymanager/nginx/snippets
$ cp -R /share/nginx_snippets/* /addon_configs/a0d7b954_nginxproxymanager/nginx/snippets
```

then you can adjust the `custom nginx configuration` like this for the `auth.example.com`

```
location / {
    include /config/nginx/snippets/proxy.conf;
    proxy_pass $forward_scheme://$server:$port;
}
```

and for every secured endpoint you can adjust the `custom nginx configuration` like this

```
include /config/nginx/snippets/authelia-location.conf;

location / {
    include /config/nginx/snippets/proxy.conf;

    # if websockets are needed include or exclude the following line
    include /config/nginx/snippets/websocket.conf;

    include /config/nginx/snippets/authelia-authrequest.conf;
    proxy_pass $forward_scheme://$server:$port;
}
```
