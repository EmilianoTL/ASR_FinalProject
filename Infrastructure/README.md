# Topología de Red GNS3: Automatización y Gestión SME

Este proyecto documenta una infraestructura de red diseñada en GNS3 para laboratorios de automatización. Implementa un esquema de enrutamiento dinámico OSPF en el Área 0, redundancia en el Core y una estación de gestión (SME) con acceso dual.

## 🏗️ Estructura de la Red
* **Borde (Edge):** Enlace con redes externas.
* **Core (R1, R2):** Distribución y transporte de tráfico.
* **Acceso/Gestión (TOR-1, TOR-2):** Gateways para servidores y usuarios finales.

---

## ⚙️ Configuraciones Detalladas por Router

Todos los routers operan bajo la versión **12.4 de IOS** y comparten una base de servicios comunes para administración:
* **Seguridad y Acceso:** Usuario `admin` con privilegio 15, dominio `redes.local` y SSHv2 habilitado con tiempo de espera de 30s.
* **Líneas VTY:** Configuración de `login local` y `transport input ssh` para gestión remota.

### 1. Edge Router
* **Router-ID:** `192.168.100.1`.
* **Interfaces:**
    * `Loopback100`: `192.168.100.1/32` (Área 0).
    * `Loopback0`: `192.168.50.1/32` (Área 0).
    * `FastEthernet1/0`: `10.0.0.1/30` (Área 0).
    * `FastEthernet1/1`: `10.0.0.5/30` (Área 0).

### 2. Router R1
* **Router-ID:** `192.168.100.2`.
* **Interfaces:**
    * `Loopback100`: `192.168.100.2/32` (Área 0).
    * `Loopback0`: `192.168.50.2/32` (Área 0).
    * `FastEthernet1/0`: `10.0.0.2/30` (Área 0).
    * `FastEthernet2/0`: `10.0.0.17/30` (Área 0).
    * `FastEthernet2/1`: `10.0.0.9/30` (Área 0).

### 3. Router R2
* **Router-ID:** `192.168.100.3`.
* **Interfaces:**
    * `Loopback100`: `192.168.100.3/32` (Área 0).
    * `Loopback0`: `192.168.50.3/32` (Área 0).
    * `FastEthernet1/1`: `10.0.0.6/30` (Área 0).
    * `FastEthernet2/0`: `10.0.0.21/30` (Área 0).
    * `FastEthernet2/1`: `10.0.0.13/30` (Área 0).

### 4. Router TOR-1 (Gateway SME)
* **Router-ID:** `192.168.100.4`.
* **Interfaces LAN:**
    * `FastEthernet1/0`: `192.168.0.1/24` (Para SME y PC1).
    * `FastEthernet1/1`: `192.168.1.1/24` (Para PC2).
* **Enlaces:** `10.0.0.18/30` y `10.0.0.14/30`.

### 5. Router TOR-2
* **Router-ID:** `192.168.100.5`.
* **Interfaces LAN:**
    * `FastEthernet1/0`: `192.168.10.1/24` (Para PC3).
    * `FastEthernet1/1`: `192.168.11.1/24` (Para PC4).
* **Enlaces:** `10.0.0.22/30` y `10.0.0.10/30`.

---

## 🖥️ Configuración de Equipos Finales

### Estación SME (Alpine Linux)
Utiliza una configuración de red persistente para separar la gestión de la conectividad a Internet:
* **eth0 (Gestión):** IP `192.168.0.10` con rutas estáticas hacia `192.168.0.0/16` y `10.0.0.0/8` vía el gateway `192.168.0.1`.
* **eth1 (Internet):** Configuración por DHCP y DNS apuntando a `8.8.8.8`.

### Hosts VPCs
* **PC1:** `192.168.0.11/24` (Gateway: `192.168.0.1`).
* **PC2:** `192.168.1.10/24` (Gateway: `192.168.1.1`).
* **PC3:** `192.168.10.10/24` (Gateway: `192.168.10.1`).
* **PC4:** `192.168.11.10/24` (Gateway: `192.168.11.1`).

---

## 🧪 Pruebas de Verificación
1.  **Conectividad OSPF:** `show ip ospf neighbor` en cualquier router debe mostrar sus vecinos en estado `FULL`.
2.  **Alcance SME:** Desde la SME, realizar `ping` a las loopbacks de administración (ej. `192.168.100.1`).
3.  **Tráfico Dividido:** `traceroute 8.8.8.8` debe salir por el nodo NAT, mientras que el tráfico a las VPCs debe pasar por el TOR-1.