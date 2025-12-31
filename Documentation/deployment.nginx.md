If you are already using nginx as a web server, you can deploy Lamb behind nginx using the following configuration. This setup uses nginx as a reverse proxy to forward requests to the appropriate services.

This configuration assumes that you have two domains:
- `lamb.lamb-project.org` for the main Lamb service
- `openwebui.lamb-project.org` for the OpenWebUI service


### nginx Configuration

File: `lamb.conf``

```nginx

server {
    server_name lamb.lamb-project.org;

    # Logs
    access_log /var/log/nginx/lamb_access.log;
    error_log /var/log/nginx/lamb_error.log;

    # Document root para archivos estáticos del frontend
    root /opt/lamb/frontend/build;
    index index.html;

    # Proxy /creator/* al backend
    location /creator/ {
        proxy_pass http://127.0.0.1:9099/creator/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy /api/* al backend
    location /api/ {
        proxy_pass http://127.0.0.1:9099/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy /lamb/* al backend (quitando el prefijo)
    location /lamb/ {
        proxy_pass http://127.0.0.1:9099/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy /kb/* al servicio de Knowledge Base
    location /kb/ {
        proxy_pass http://127.0.0.1:9090/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Redirigir /openwebui/* al subdominio
    location /openwebui/ {
        return 301 http://openwebui-lamb.lamb-project.org$request_uri;
    }

    # SPA fallback - servir index.html para rutas del frontend
    location / {
        try_files $uri $uri/ /index.html;
    }

    listen [::]:443 ssl ipv6only=on; # managed by Certbot
    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/lamb.lamb-project.org/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/lamb.lamb-project.org/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot

}
server {
    if ($host = lamb.lamb-project.org) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen 80;
    listen [::]:80;
    server_name lamb.lamb-project.org;
    return 404; # managed by Certbot


}

```

File: `openwebui.conf`

```nginx

server {
    server_name openwebui-lamb.lamb-project.org;

    # Logs
    access_log /var/log/nginx/openwebui_access.log;
    error_log /var/log/nginx/openwebui_error.log;

    location / {
        proxy_pass http://127.0.0.1:8080/;
        proxy_http_version 1.1;
        
        # Headers estándar
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Soporte WebSocket
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeout largo para WebSockets
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    listen [::]:443 ssl; # managed by Certbot
    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/openwebui-lamb.lamb-project.org/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/openwebui-lamb.lamb-project.org/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot

}

server {
    if ($host = openwebui-lamb.lamb-project.org) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen 80;
    listen [::]:80;
    server_name openwebui-lamb.lamb-project.org;
    return 404; # managed by Certbot


}

```


