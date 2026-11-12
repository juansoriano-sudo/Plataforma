# FinandinaMonitor — Docker

Blazor Server (.NET 10) empaquetado en un contenedor Linux. Un solo proceso sirve toda la
aplicación (UI + lógica) por HTTPS en el puerto 8080 interno, publicado en el host como
**56024** (el puerto al que ya se conectan los usuarios: `https://<host>:56024/`).

## Requisitos antes de levantar el contenedor

1. **Certificado HTTPS** en `./certs/finandina.pfx` (no se versiona, está en `.gitignore`).
   - Si quieres reutilizar el mismo certificado de desarrollo que ya usan los usuarios hoy,
     expórtalo **desde la máquina donde corre la app actualmente**:
     ```powershell
     dotnet dev-certs https -ep .\certs\finandina.pfx -p "<una_contraseña>"
     ```
   - Copia ese `finandina.pfx` al servidor/equipo donde se va a correr Docker, dentro de
     `./certs/`.
   - Pon esa misma contraseña en `.env` como `CERT_PASSWORD`.

2. **Archivo de credenciales NTLM** en `./ntlm_user` (no se versiona). Es la solución
   temporal mientras el DBA crea el login dedicado de SQL Server
   (`scripts/create-motorfirma-login.sql`). Formato (una sola línea):
   ```
   FINANDINA:tu_usuario:tu_contraseña_de_dominio
   ```
   Hay una plantilla en `ntlm_user.example`. **Esta contraseña cambia si cambias tu clave de
   dominio** — hay que actualizar el archivo cuando eso pase.

   Cuando el DBA entregue el login dedicado de SQL Server:
   - Completa `SQLSERVER_USER` / `SQLSERVER_PASSWORD` en `.env`.
   - En `docker-compose.yml`, cambia la cadena `ConnectionStrings__FinandinaDb` a:
     `Server=...;Database=MotorFirma;User Id=${SQLSERVER_USER};Password=${SQLSERVER_PASSWORD};Encrypt=True;TrustServerCertificate=True;`
   - Quita `NTLM_USER_FILE`, el volumen de `./ntlm_user` y el paquete `gss-ntlmssp` del
     `Dockerfile`.

3. **`.env`** con los valores reales (ver `.env.example`):
   - `CERT_PASSWORD`
   - `MARIADB_LOGS_PASSWORD`
   - `SQLSERVER_USER` / `SQLSERVER_PASSWORD` (pendientes del DBA)

## Comandos

```bash
# Construir la imagen
docker compose build

# Iniciar (en segundo plano)
docker compose up -d

# Ver estado y healthcheck
docker ps --filter name=finandina-monitor

# Ver logs en vivo
docker compose logs -f finandina-monitor

# Detener (mantiene la imagen y los volúmenes)
docker compose down

# Actualizar después de un cambio de código
docker compose build
docker compose up -d
```

## Verificar antes de levantar en el servidor definitivo

Antes de correr `docker compose up` en el servidor donde van a quedar escuchando los
usuarios, confirma qué está ocupando hoy el puerto 56024 y detenlo tú mismo (no lo hace
Docker automáticamente):

```powershell
# Windows
netstat -ano | findstr :56024
```
```bash
# Linux
sudo ss -tlnp | grep 56024
```

## Si algo falla: volver a la forma anterior

```bash
docker compose down
```

y vuelve a iniciar la aplicación de la forma en que corría antes (directamente con
`dotnet FinandinaMonitor.UI.dll` o como se estuviera lanzando en Windows). El contenedor no
modifica nada fuera de sí mismo: no toca IIS, servicios de Windows, ni la base de datos.

## Qué quedó pendiente / decisiones tomadas

- **Login SQL Server dedicado**: aún no existe. Se usa NTLM (`gss-ntlmssp`) con una cuenta
  de dominio personal como solución temporal (ver arriba). Es mantenimiento recurrente
  (cambia si cambia la contraseña de dominio) — no dejarlo así indefinidamente.
- **Timeout de APIs externas**: no se identificó con certeza cuál endpoint es el que tarda
  ~2 minutos (FirmaApi, ReprocessApi o SignatureApi), así que se subió el timeout de los
  tres `HttpClient` a 3 minutos (`FinandinaMonitor.UI/Program.cs`). Si se identifica el
  endpoint exacto, se puede bajar el timeout de los otros dos.
- **Healthcheck**: se agregó `GET /healthz` (`Program.cs`) y el `HEALTHCHECK` del
  `Dockerfile` lo consulta cada 30s.
- **Persistencia**: los históricos de reprocesos y alertas de monitoreo viven en memoria
  (`HistoricoReprocesoStore`, `AlertaMonitoreoStore`) — se pierden en cada reinicio, igual
  que antes de dockerizar (no es un cambio de comportamiento). Lo único que se persiste en
  un volumen es la llave de Data Protection (`dataprotection-keys`), para que un reinicio
  del contenedor no invalide las sesiones/formularios abiertos de los usuarios.
