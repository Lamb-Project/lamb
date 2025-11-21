If you are already using Apache as a web server, you can deploy Lamb behind Apache using the following configuration. This setup uses Apache as a reverse proxy to forward requests to the appropriate services.

This configuration assumes that you have two domains:
- `lamb.lamb-project.org` for the main Lamb service
- `openwebui.lamb-project.org` for the OpenWebUI service

### Apache Configuration
File: `/etc/apache2/sites-available/lamb.conf``

```apache
<VirtualHost *:80>
        ServerName lamb.lamb-project.org
        ServerAdmin admin@lamb-project.org

        # Enable proxy modules
        # ProxyPreserveHost On
        # ProxyRequests Off

        # Proxy rules
        # ProxyPass / http://localhost:9099/
        # ProxyPassReverse / http://localhost:9099/

        RewriteEngine on
        RewriteCond %{SERVER_NAME} =lamb.lamb-project.org
        RewriteRule ^ https://%{SERVER_NAME}%{REQUEST_URI} [END,NE,R=permanent]

        # Logging
        ErrorLog ${APACHE_LOG_DIR}/lamb_error.log
        CustomLog ${APACHE_LOG_DIR}/lamb_access.log combined

</VirtualHost>
```

File: `/etc/apache2/sites-available/lamb-ssl.conf`
```apache
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName lamb.lamb-project.org
    ServerAdmin admin@lamb-project.org

    # Document root for static files
    DocumentRoot /opt/lamb/frontend/build

    <Directory /opt/lamb/frontend/build>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted
    </Directory>

    # Enable proxy modules
    ProxyPreserveHost On
    ProxyRequests Off

    # Proxy /creator/* to backend
    ProxyPass /creator/ http://localhost:9099/creator/
    ProxyPassReverse /creator/ http://localhost:9099/creator/

    # Proxy /api/* to backend
    ProxyPass /api/ http://localhost:9099/api/
    ProxyPassReverse /api/ http://localhost:9099/api/

    # Proxy /lamb/* to backend (with prefix stripping)
    ProxyPass /lamb/ http://localhost:9099/
    ProxyPassReverse /lamb/ http://localhost:9099/

    # Proxy /kb/* to kb service (with prefix stripping)
    ProxyPass /kb/ http://localhost:9090/
    ProxyPassReverse /kb/ http://localhost:9090/

    # Redirect legacy /openwebui/* paths to new subdomain
    RewriteEngine On
    RewriteRule ^/openwebui/(.*)$ https://openwebui.lamb-project.org/$1 [R=301,L]

    # SPA fallback - serve index.html for all non-proxied, non-existent routes
    # Use explicit document root check
    RewriteCond /opt/lamb/frontend/build%{REQUEST_URI} !-f
    RewriteCond /opt/lamb/frontend/build%{REQUEST_URI} !-d
    RewriteCond %{REQUEST_URI} !^/creator/
    RewriteCond %{REQUEST_URI} !^/api/
    RewriteCond %{REQUEST_URI} !^/lamb/
    RewriteCond %{REQUEST_URI} !^/kb/
    RewriteRule ^ /index.html [L]
    
    # Logging
    ErrorLog ${APACHE_LOG_DIR}/lamb_error.log
    CustomLog ${APACHE_LOG_DIR}/lamb_access.log combined
    # LogLevel debug rewrite:trace6

    SSLCertificateFile /etc/letsencrypt/live/lamb.lamb-project.org/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/lamb.lamb-project.org/privkey.pem
    Include /etc/letsencrypt/options-ssl-apache.conf
</VirtualHost>
</IfModule>
```

File: `/etc/apache2/sites-available/openwebui.conf`
```apache
<VirtualHost *:80>
    ServerName openwebui.lamb-project.org
    ServerAlias www.openwebui.lamb-project.org

    # Redirect all HTTP to HTTPS
    RewriteEngine on
    RewriteCond %{SERVER_NAME} =openwebui.lamb-project.org [OR]
    RewriteCond %{SERVER_NAME} =www.openwebui.lamb-project.org
    RewriteRule ^ https://%{SERVER_NAME}%{REQUEST_URI} [END,NE,R=permanent]

    ErrorLog ${APACHE_LOG_DIR}/openwebui_error.log
    LogLevel warn
</VirtualHost>
```

File: `/etc/apache2/sites-available/openwebui-ssl.conf`
```apache
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName openwebui.lamb-project.org
    ServerAlias www.openwebui.lamb-project.org

    # Enable proxy modules
    ProxyRequests Off
    ProxyPreserveHost On

    # ProxyPass for HTTP
    ProxyPass / http://localhost:8080/
    ProxyPassReverse / http://localhost:8080/

    # WebSocket support
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} websocket [NC]
    RewriteCond %{HTTP:Connection} upgrade [NC]
    RewriteRule /(.*) ws://localhost:8080/$1 [P,L]

    # Proxy settings
    <Proxy *>
        Require all granted
    </Proxy>

    # ErrorLog and LogLevel for debugging
    ErrorLog ${APACHE_LOG_DIR}/openwebui_error.log
    LogLevel warn

    SSLCertificateFile /etc/letsencrypt/live/openwebui.lamb-project.org/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/openwebui.lamb-project.org/privkey.pem
    Include /etc/letsencrypt/options-ssl-apache.conf
</VirtualHost>
</IfModule>
```
### Enabling the Configuration
To enable the new site configurations and required modules, run the following commands:

```bash
sudo a2ensite lamb.conf
sudo a2ensite lamb-ssl.conf
sudo a2ensite openwebui.conf
sudo a2ensite openwebui-ssl.conf
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod proxy_wstunnel
sudo a2enmod rewrite
sudo a2enmod ssl
```

### Restart Apache
After making these changes, restart Apache to apply the new configuration:

```bash
sudo systemctl restart apache2
```

