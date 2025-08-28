# Opción A: Acceso por VNC clásico (TigerVNC) usando túnel SSH

Estas instrucciones configuran un servidor VNC ligero (Openbox) en Ubuntu y conectan de forma segura desde tu PC mediante un túnel SSH. Diseñado para servidores sin entorno gráfico (sin DISPLAY/X11).

---

## 1) Instalar paquetes en el servidor (Ubuntu)

```bash
sudo apt update
sudo apt install -y tigervnc-standalone-server xorg openbox
```

- tigervnc-standalone-server: servidor VNC.
- xorg + openbox: sesión gráfica mínima y estable.

---

## 2) Configurar `~/.vnc/xstartup`

```bash
mkdir -p ~/.vnc
cat > ~/.vnc/xstartup << 'EOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec openbox-session
EOF
chmod +x ~/.vnc/xstartup
```

---

## 3) Crear contraseña VNC (primera vez)

```bash
vncpasswd
```

- Define una contraseña para acceder por VNC.

---

## 4) Iniciar VNC en el display :1 (puerto 5901), solo para localhost

```bash
vncserver :1 -localhost yes -geometry 1280x800
```

- `:1` → escucha en 5901.
- `-localhost yes` → solo acepta conexiones locales (recomendado para usar con túnel SSH).
- Cambia `-geometry` si necesitas otra resolución.

Verifica que esté escuchando:

```bash
ss -ltnp | grep 590
```

Debes ver `LISTEN` en `127.0.0.1:5901` o `::1:5901`.

---

## 5) Crear el túnel SSH desde tu máquina

El objetivo es mapear el puerto local a `localhost:5901` del servidor.

- Desde Windows (PowerShell/OpenSSH):

```powershell
ssh -L 5901:localhost:5901 apustuak@<IP_O_DOMINIO_DEL_SERVIDOR>
```

- Desde otro Linux/macOS (bash):

```bash
ssh -L 5901:localhost:5901 apustuak@<IP_O_DOMINIO_DEL_SERVIDOR>
```

Mantén esta sesión abierta mientras uses VNC.

---

## 6) Conectarte con el visor VNC

- Abre RealVNC (o TigerVNC Viewer) en tu PC.
- En “VNC Server” escribe: `127.0.0.1:5901`
- Introduce la contraseña creada con `vncpasswd`.

---

## 7) Parar el servidor VNC

```bash
vncserver -kill :1
```

---

## Solución de problemas

- __Connection refused__: el túnel apunta a un puerto donde no hay VNC. Asegúrate de haber lanzado `vncserver :1` y tuneliza `-L 5901:localhost:5901`.
- __Pantalla negra o sesión no carga__: revisa `~/.vnc/xstartup` y permisos (`chmod +x`). Prueba `openbox-session` como arriba.
- __No quieres usar :1__: puedes usar `:0` (puerto 5900) si lo prefieres:
  - `vncserver :0 -localhost yes`
  - Túnel: `ssh -L 5900:localhost:5900 apustuak@<IP>` y conecta a `127.0.0.1:5900`.
- __Cambiar resolución__: reinicia con `-geometry 1600x900` (u otra).
- __Errores de puertos ocupados__: mata sesiones previas y borra locks si es necesario:
  ```bash
  vncserver -kill :1 || true
  rm -f /tmp/.X1-lock /tmp/.X11-unix/X1
  ```

---

## Seguridad y buenas prácticas

- Mantén `-localhost yes` y accede siempre vía túnel SSH.
- Usa claves SSH en lugar de contraseña si es posible.
- No expongas 5900/5901 en el firewall público.

---

## Comandos útiles

Listar sesiones VNC activas:
```bash
vncserver -list
```

Logs de la sesión VNC:
```bash
ls -1 ~/.vnc/*:1.log
 tail -n 100 ~/.vnc/*:1.log
```

Reiniciar sesión VNC limpiamente:
```bash
vncserver -kill :1
vncserver :1 -localhost yes -geometry 1280x800
```
