# Optional Moodle connector (0.7)

The connector is disabled by default. Before enabling it, generate a dedicated
Fernet key using the backend Python environment:

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set `LAMB_MOODLE_ENCRYPTION_KEY` in the environment file used by Compose
(`.env.next.example` includes the setting), or in the backend environment for a
non-container installation. Recreate the LAMB container after changing its
environment. Keep the key stable and back it up separately from the database.
Changing or losing it makes existing stored Moodle tokens unreadable; affected
creators must reconnect. There is no plaintext or application-signing-key fallback.

In the Moodle page, an organization administrator enables the connector and sets
one allowed Moodle base URL. Start with readonly mode. Forum posting requires
full mode and the forum write group; saving grades additionally requires the
separate grade flag. Both write paths require user approval in the LAMB LEGATUS.
The administrator sees the disclosure that student names, posts and grades reach
the configured AAC model provider.

Each creator connects their own account using a mobile-service token or a fresh
Moodle mobile QR passport. The backend verifies the site and account before
storing the encrypted token. Moodle must expose the mobile web services, and the
account needs instructor permissions for course-wide reads. Moodle's own
permissions continue to apply. Disconnect on this page removes the stored token.
Do not paste credentials into an agent conversation.


### Connecting with a QR image

On the LAMB Moodle page, select **QR code image** and upload a fresh PNG, JPEG or
WebP screenshot of your Moodle automatic-login QR code, then click **Connect with
QR image**. The complete QR code and its border should be visible. Images are
limited to 5 MiB and 12 megapixels and are decoded in memory, not stored as
uploaded documents or sent to the AAC. The selected image is cleared after each
attempt. An expired or already-used passport requires a fresh QR code.

The Moodle administrator must enable automatic-login QR codes on an HTTPS site.
A QR containing only the site address cannot authenticate you. LAMB also rejects
QR codes for a site other than the organization's configured Moodle URL.
**Advanced options** retain pasted mobile passports and mobile-service tokens.
