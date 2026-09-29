"""
=============================================================================
GENERADOR DE DATOS SINTÉTICOS REALISTAS - AEROLINEA_DB_V2 COMPATIBLE CON POWER BI (MySQL 8+)
=============================================================================
Perfil compacto orientado a Power BI / portafolio.
Objetivo: ~45.000-50.000 filas totales, distribuidas de forma coherente.
Cobertura temporal: 2025-11-01 a 2025-11-30.
Semilla fija: 42 (reproducible).
Sin dependencias externas: solo librería estándar de Python.

Este generador está diseñado para el esquema aerolinea_db_v2 y prioriza:
- Diferencias reales entre rutas (frecuencia, ocupación y precio).
- Estacionalidad mensual.
- Demanda monotónica antes del vuelo.
- Capacidad y cabinas consistentes con el avión asignado.
- Asientos, tarifas, inventario y segmentos coherentes entre sí.
- Pagos iguales a la suma de los segmentos de cada PNR.
=============================================================================
"""

import os
import sys
import random
import math
from datetime import datetime, date, time, timedelta
from collections import defaultdict, Counter

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SEED = 42
random.seed(SEED)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_v2")
BATCH_SIZE = 500
SCHEMA_NAME = "aerolinea_db_v2"

FECHA_INICIO = date(2025, 11, 1)
FECHA_FIN = date(2025, 11, 30)
FECHA_REFERENCIA = datetime(2025, 12, 15, 12, 0, 0)  # Todo el periodo ya ocurrió
NUM_PASAJEROS = 2500

# Flota compacta: suficiente variedad sin inflar el modelo.
CONFIG_FLOTA = [
    # modelo, distribución {cabina: asientos}, cantidad
    ("Boeing 787-8 Dreamliner", {4: 8, 3: 28, 2: 34, 1: 180}, 1),
    ("Airbus A330-200",         {3: 30, 2: 24, 1: 198}, 1),
    ("Airbus A320neo",          {2: 24, 1: 156}, 5),
    ("ATR 72-600",              {2: 8,  1: 62}, 1),
]

# Objetivo de vuelos específicos por par (ida + vuelta) durante 2024-2025.
# La distribución desigual evita el patrón artificial de "todas las rutas iguales".
RUTAS = [
    # orig, dest, salida ida, duración min, días activos, total par, ocupación base, tipo, precio eco, modelos permitidos
    # El total de vuelos del mes es 210 (~7 vuelos diarios).
    ("BOG", "MDE", time(6, 10),   55, [1,2,3,4,5,6,7], 44, 0.77, "troncal",      190000, ["Airbus A320neo"]),
    ("BOG", "CLO", time(7, 0),    60, [1,2,3,4,5,6,7], 30, 0.72, "troncal",      210000, ["Airbus A320neo"]),
    ("BOG", "CTG", time(8, 0),    85, [1,2,3,4,5,6,7], 28, 0.78, "turistica",    290000, ["Airbus A320neo"]),
    ("BOG", "BAQ", time(7, 30),   90, [1,2,3,4,5,6,7], 22, 0.69, "troncal",      280000, ["Airbus A320neo"]),
    ("BOG", "SMR", time(9, 0),    90, [1,3,5,6,7],     18, 0.75, "turistica",    300000, ["Airbus A320neo"]),
    ("BOG", "ADZ", time(10, 0),  135, [2,4,6,7],       14, 0.80, "turistica",    520000, ["Airbus A320neo"]),
    ("MDE", "CTG", time(10, 15),  70, [1,3,5,7],       14, 0.66, "turistica",    240000, ["Airbus A320neo"]),
    ("BOG", "MIA", time(7, 20),  240, [1,3,5,7],       10, 0.72, "internacional",1200000, ["Airbus A330-200", "Airbus A320neo"]),
    ("BOG", "MAD", time(14, 45), 590, [2,4,6],          8, 0.79, "internacional",3400000, ["Boeing 787-8 Dreamliner"]),
    ("BOG", "LET", time(11, 30), 125, [2,5,7],          8, 0.59, "regional",     470000, ["Airbus A320neo", "ATR 72-600"]),
    ("BOG", "PSO", time(8, 45),   85, [1,4],            8, 0.55, "regional",     330000, ["ATR 72-600", "Airbus A320neo"]),
    ("MDE", "MIA", time(8, 20),  225, [3,6],            6, 0.69, "internacional",1100000, ["Airbus A330-200", "Airbus A320neo"]),
]

# ---------- Utilidades ----------

def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def ascii_simple(s):
    tabla = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return s.translate(tabla)


def escapar_sql(val):
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return f"{val:.2f}"
    if isinstance(val, datetime):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'"
    if isinstance(val, date):
        return f"'{val.strftime('%Y-%m-%d')}'"
    if isinstance(val, time):
        return f"'{val.strftime('%H:%M:%S')}'"
    txt = str(val).replace("'", "''")
    return f"'{txt}'"


def escribir_sql(nombre_archivo, tabla, columnas, filas):
    ruta = os.path.join(OUTPUT_DIR, nombre_archivo)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(f"-- {tabla}: {len(filas):,} registros\n")
        f.write(f"USE {SCHEMA_NAME};\nSET NAMES utf8mb4;\n\n")
        if not filas:
            return ruta
        cols = ", ".join(columnas)
        for i in range(0, len(filas), BATCH_SIZE):
            lote = filas[i:i+BATCH_SIZE]
            f.write(f"INSERT INTO {tabla} ({cols}) VALUES\n")
            f.write(",\n".join(
                "  (" + ", ".join(escapar_sql(v) for v in fila) + ")"
                for fila in lote
            ))
            f.write(";\n\n")
    return ruta


def repartir_entero(total, pesos):
    """Distribuye un entero según pesos, preservando la suma exacta."""
    if total <= 0:
        return [0] * len(pesos)
    s = sum(pesos)
    raw = [total * p / s for p in pesos]
    base = [int(math.floor(x)) for x in raw]
    faltan = total - sum(base)
    orden = sorted(range(len(raw)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in orden[:faltan]:
        base[i] += 1
    return base


def weighted_sample_without_replacement(items, weights, k):
    items = list(items)
    weights = list(weights)
    out = []
    k = min(k, len(items))
    for _ in range(k):
        idx = random.choices(range(len(items)), weights=weights, k=1)[0]
        out.append(items.pop(idx))
        weights.pop(idx)
    return out


def factor_estacional(tipo, mes):
    if tipo == "turistica":
        return {1:1.12, 3:1.07, 4:1.08, 6:1.12, 7:1.14, 12:1.16, 9:0.92, 10:0.93}.get(mes, 1.0)
    if tipo == "internacional":
        return {1:1.05, 6:1.08, 7:1.10, 12:1.12, 2:0.96, 9:0.96}.get(mes, 1.0)
    if tipo == "troncal":
        return {2:1.03, 3:1.03, 4:1.02, 5:1.03, 8:1.03, 9:1.02, 10:1.03, 11:1.03, 1:0.96, 7:0.97}.get(mes, 1.0)
    return {6:1.04, 7:1.05, 12:1.05, 2:0.96}.get(mes, 1.0)


# ---------- Maestros ----------

def generar_aeropuertos():
    data = [
        ("BOG","Aeropuerto Internacional El Dorado","Bogotá","Colombia","America/Bogota"),
        ("MDE","Aeropuerto Internacional José María Córdova","Medellín","Colombia","America/Bogota"),
        ("CLO","Aeropuerto Internacional Alfonso Bonilla Aragón","Cali","Colombia","America/Bogota"),
        ("CTG","Aeropuerto Internacional Rafael Núñez","Cartagena","Colombia","America/Bogota"),
        ("BAQ","Aeropuerto Internacional Ernesto Cortissoz","Barranquilla","Colombia","America/Bogota"),
        ("SMR","Aeropuerto Internacional Simón Bolívar","Santa Marta","Colombia","America/Bogota"),
        ("BGA","Aeropuerto Internacional Palonegro","Bucaramanga","Colombia","America/Bogota"),
        ("PEI","Aeropuerto Internacional Matecaña","Pereira","Colombia","America/Bogota"),
        ("CUC","Aeropuerto Internacional Camilo Daza","Cúcuta","Colombia","America/Bogota"),
        ("ADZ","Aeropuerto Internacional Gustavo Rojas Pinilla","San Andrés","Colombia","America/Bogota"),
        ("AXM","Aeropuerto Internacional El Edén","Armenia","Colombia","America/Bogota"),
        ("PSO","Aeropuerto Antonio Nariño","Pasto","Colombia","America/Bogota"),
        ("MTR","Aeropuerto Los Garzones","Montería","Colombia","America/Bogota"),
        ("VUP","Aeropuerto Alfonso López Pumarejo","Valledupar","Colombia","America/Bogota"),
        ("NVA","Aeropuerto Benito Salas","Neiva","Colombia","America/Bogota"),
        ("IBE","Aeropuerto Perales","Ibagué","Colombia","America/Bogota"),
        ("EYP","Aeropuerto El Alcaraván","Yopal","Colombia","America/Bogota"),
        ("FLA","Aeropuerto Gustavo Artunduaga","Florencia","Colombia","America/Bogota"),
        ("RCH","Aeropuerto Almirante Padilla","Riohacha","Colombia","America/Bogota"),
        ("LET","Aeropuerto Internacional Alfredo Vásquez Cobo","Leticia","Colombia","America/Bogota"),
        ("MIA","Aeropuerto Internacional de Miami","Miami","Estados Unidos","America/New_York"),
        ("JFK","Aeropuerto Internacional John F. Kennedy","Nueva York","Estados Unidos","America/New_York"),
        ("MCO","Aeropuerto Internacional de Orlando","Orlando","Estados Unidos","America/New_York"),
        ("MAD","Aeropuerto Adolfo Suárez Madrid-Barajas","Madrid","España","Europe/Madrid"),
        ("BCN","Aeropuerto Josep Tarradellas Barcelona-El Prat","Barcelona","España","Europe/Madrid"),
        ("LIM","Aeropuerto Internacional Jorge Chávez","Lima","Perú","America/Lima"),
        ("PTY","Aeropuerto Internacional de Tocumen","Ciudad de Panamá","Panamá","America/Panama"),
        ("MEX","Aeropuerto Internacional Benito Juárez","Ciudad de México","México","America/Mexico_City"),
        ("SCL","Aeropuerto Internacional Arturo Merino Benítez","Santiago","Chile","America/Santiago"),
        ("EZE","Aeropuerto Internacional Ministro Pistarini","Buenos Aires","Argentina","America/Argentina/Buenos_Aires"),
    ]
    filas = [(i+1, *r) for i, r in enumerate(data)]
    mapa = {r[1]: r[0] for r in filas}
    return filas, mapa


def generar_cabinas():
    return [
        (1,"ECO","Económica","Cabina principal estándar con servicios esenciales."),
        (2,"PRE","Premium Economy","Mayor espacio para piernas y prioridad de embarque."),
        (3,"BUS","Business Class","Producto premium con mayor espacio y servicios ejecutivos."),
        (4,"FIR","Primera Clase","Cabina de máxima privacidad y servicio personalizado."),
    ]


def generar_flota_y_asientos():
    aviones, distribuciones, asientos = [], [], []
    asientos_por_avion_cabina = defaultdict(list)
    capacidad_por_avion = {}
    cabinas_por_avion = defaultdict(dict)
    avion_por_modelo = defaultdict(list)

    id_avion = 1
    id_distribucion = 1
    id_asiento = 1
    matricula = 6101

    for modelo, dist, cantidad in CONFIG_FLOTA:
        for _ in range(cantidad):
            estado = "Activo"
            capacidad_total = sum(dist.values())
            # Se conserva capacidad_total por compatibilidad con el modelo actual de Power BI.
            aviones.append((id_avion, f"HK-{matricula}", modelo, capacidad_total, estado))
            avion_por_modelo[modelo].append(id_avion)
            matricula += 1
            capacidad_por_avion[id_avion] = capacidad_total
            cabinas_por_avion[id_avion] = dict(dist)

            for cab in sorted(dist):
                # Se conserva avion_clase_asientos con sus columnas originales.
                distribuciones.append((id_distribucion, id_avion, cab, dist[cab]))
                id_distribucion += 1

            fila_num = 1
            for cab in [4,3,2,1]:
                if cab not in dist:
                    continue
                cantidad_cab = dist[cab]
                if cab in (4,3):
                    letras = [('A','Ventana'),('C','Pasillo'),('D','Pasillo'),('F','Ventana')]
                elif capacidad_por_avion[id_avion] <= 70:
                    letras = [('A','Ventana'),('C','Pasillo'),('D','Pasillo'),('F','Ventana')]
                else:
                    letras = [('A','Ventana'),('B','Medio'),('C','Pasillo'),('D','Pasillo'),('E','Medio'),('F','Ventana')]
                hechos = 0
                while hechos < cantidad_cab:
                    for letra, ubic in letras:
                        if hechos >= cantidad_cab:
                            break
                        codigo = f"{fila_num}{letra}"
                        asientos.append((id_asiento,id_avion,cab,codigo,fila_num,letra,ubic))
                        asientos_por_avion_cabina[(id_avion,cab)].append(id_asiento)
                        id_asiento += 1
                        hechos += 1
                    fila_num += 1
            id_avion += 1

    return aviones, distribuciones, asientos, asientos_por_avion_cabina, capacidad_por_avion, cabinas_por_avion, avion_por_modelo


def generar_tarifas_reglas():
    tarifas = [
        (1,"ECO-XS",1,0,0),(2,"ECO-S",1,0,0),(3,"ECO-M",1,1,0),(4,"ECO-L",1,1,1),
        (5,"PRE-S",2,1,0),(6,"PRE-F",2,1,1),
        (7,"BUS-P",3,1,0),(8,"BUS-C",3,1,1),(9,"BUS-F",3,1,1),
        (10,"FIR-F",4,1,1),
    ]
    reglas_base = [
        (1,"Cargo por cambio de fecha",160000,"Aplica antes de la salida."),
        (1,"Penalidad por no show",220000,"Aplica cuando el pasajero no se presenta."),
        (1,"Equipaje de bodega adicional",95000,"Valor por pieza adicional."),
        (2,"Cargo por cambio de fecha",130000,"Sujeto a disponibilidad."),
        (2,"Primera maleta de bodega",75000,"Pieza estándar de hasta 23 kg."),
        (3,"Cargo por cambio de fecha",60000,"Más diferencia tarifaria si aplica."),
        (3,"Equipaje de bodega incluido",0,"Incluye una pieza de hasta 23 kg."),
        (4,"Cambio de fecha",0,"Sin penalidad; puede aplicar diferencia tarifaria."),
        (4,"Reembolso",70000,"Cargo administrativo por reembolso."),
        (5,"Cargo por cambio de fecha",80000,"Más diferencia tarifaria si aplica."),
        (5,"Equipaje de bodega",0,"Incluye dos piezas."),
        (6,"Cambio de fecha",0,"Cambio sin penalidad."),
        (6,"Reembolso total",0,"Reembolso permitido."),
        (7,"Cargo por cambio de fecha",100000,"Tarifa Business promocional."),
        (7,"Acceso a sala VIP",0,"Sujeto a aeropuerto."),
        (8,"Cambio y reembolso",0,"Sin penalidad."),
        (8,"Equipaje prioritario",0,"Dos piezas de hasta 32 kg."),
        (9,"Flexibilidad total",0,"Cambios y reembolsos sin penalidad."),
        (10,"Suite privada",0,"Servicio de Primera Clase."),
        (10,"Transfer VIP",0,"Sujeto a disponibilidad en destino."),
        (10,"Reembolso total",0,"Sin penalidad."),
    ]
    reglas = [(i+1, tarifa, tipo, valor, desc) for i,(tarifa,tipo,valor,desc) in enumerate(reglas_base)]
    return tarifas, reglas


# ---------- Programación y vuelos ----------

def generar_programacion(mapa_aeropuertos):
    vuelos_prog, dias_prog = [], []
    info = {}
    id_prog = 1
    id_dia = 1
    numero = 201
    nombres_dia = {1:"Lunes",2:"Martes",3:"Miércoles",4:"Jueves",5:"Viernes",6:"Sábado",7:"Domingo"}

    for ruta_idx, (orig,dest,h_salida,dur,dias,total_par,occ_base,tipo,precio_base,modelos) in enumerate(RUTAS, start=1):
        ida_target = (total_par + 1) // 2
        vuelta_target = total_par // 2

        def agregar(o,d,h,days,target,dir_bias):
            nonlocal id_prog, id_dia, numero
            salida_dt = datetime.combine(date(2024,1,1), h)
            llegada_dt = salida_dt + timedelta(minutes=dur)
            h_llegada = llegada_dt.time()
            dias_llegada = (llegada_dt.date() - salida_dt.date()).days
            vuelos_prog.append((
                id_prog, f"AV{numero}", mapa_aeropuertos[o], mapa_aeropuertos[d],
                h, h_llegada, dias_llegada, FECHA_INICIO, FECHA_FIN, 1
            ))
            for ds in days:
                dias_prog.append((id_dia, id_prog, ds, nombres_dia[ds]))
                id_dia += 1
            info[id_prog] = {
                "orig":o,"dest":d,"dur":dur,"dias":list(days),"target":target,
                "occ_base":clamp(occ_base+dir_bias,0.45,0.95),"tipo":tipo,
                "precio_base":precio_base,"modelos":list(modelos),
                "hora_salida":h,"dias_llegada":dias_llegada,"ruta_idx":ruta_idx,
            }
            id_prog += 1
            numero += 1

        agregar(orig,dest,h_salida,dias,ida_target,0.01)
        # Regreso: salida con margen razonable tras la llegada; si cruza medianoche, queda en hora local simplificada.
        h_reg = (datetime.combine(date(2024,1,1), h_salida) + timedelta(minutes=dur+90)).time()
        agregar(dest,orig,h_reg,dias,vuelta_target,-0.01)

    return vuelos_prog, dias_prog, info


def _peso_fecha(info, f):
    w = factor_estacional(info["tipo"], f.month)
    # Viernes/domingo mejor para ocio; lunes/jueves algo mejor para troncales.
    if info["tipo"] == "turistica" and f.isoweekday() in (5,6,7):
        w *= 1.12
    if info["tipo"] == "troncal" and f.isoweekday() in (1,4,5):
        w *= 1.08
    return w


def generar_vuelos_especificos(vuelos_prog, info, avion_por_modelo):
    filas = []
    used_plane_day = defaultdict(set)
    tmp = []

    for vp in vuelos_prog:
        id_prog = vp[0]
        inf = info[id_prog]
        elegibles = []
        pesos = []
        f = FECHA_INICIO
        while f <= FECHA_FIN:
            if f.isoweekday() in inf["dias"]:
                elegibles.append(f)
                pesos.append(_peso_fecha(inf, f))
            f += timedelta(days=1)
        fechas = weighted_sample_without_replacement(elegibles, pesos, inf["target"])
        for fv in fechas:
            tmp.append((fv, id_prog))

    tmp.sort(key=lambda x: (x[0], info[x[1]]["hora_salida"], x[1]))

    irregularidades = [
        "Condiciones meteorológicas", "Restricción operacional del aeropuerto",
        "Inspección técnica no programada", "Congestión de tráfico aéreo",
        "Rotación tardía de la aeronave"
    ]

    for id_esp, (fv, id_prog) in enumerate(tmp, start=1):
        inf = info[id_prog]
        pool = []
        for modelo in inf["modelos"]:
            pool.extend(avion_por_modelo.get(modelo, []))
        disponibles = [a for a in pool if a not in used_plane_day[fv]] or pool
        id_avion = random.choice(disponibles)
        used_plane_day[fv].add(id_avion)

        r = random.random()
        if r < 0.90:
            estado = "Realizado"
        elif r < 0.95:
            estado = "Demorado"
        elif r < 0.98:
            estado = "Cancelado"
        else:
            estado = "Desviado"

        salida_prog = datetime.combine(fv, inf["hora_salida"])
        llegada_prog = salida_prog + timedelta(minutes=inf["dur"])
        motivo = None
        if estado == "Cancelado":
            salida_real = None
            llegada_real = None
            motivo = random.choice(irregularidades)
        elif estado == "Demorado":
            delay = random.randint(45, 180)
            salida_real = salida_prog + timedelta(minutes=delay)
            llegada_real = llegada_prog + timedelta(minutes=delay + random.randint(-5,20))
            motivo = random.choice(irregularidades)
        elif estado == "Desviado":
            delay = random.randint(10, 60)
            salida_real = salida_prog + timedelta(minutes=delay)
            llegada_real = llegada_prog + timedelta(minutes=delay + random.randint(20,70))
            motivo = "Desvío operacional por " + random.choice(["meteorología", "restricción aeroportuaria", "emergencia médica"])
        else:
            delay = random.randint(-10, 28)
            salida_real = salida_prog + timedelta(minutes=delay)
            llegada_real = llegada_prog + timedelta(minutes=delay + random.randint(-8,15))

        filas.append((id_esp,id_prog,id_avion,fv,estado,salida_real,llegada_real,motivo))

    return filas


# ---------- Pasajeros ----------

def generar_pasajeros_documentos(cantidad):
    masc = ["Carlos","Juan","Andrés","Felipe","Mateo","Santiago","David","Alejandro","Daniel","Sebastián","Diego","Camilo","Nicolás","Leonardo","Gabriel","Julián","Samuel","Lucas","Manuel","José","Federico","Eduardo","Mario"]
    fem = ["María","Laura","Valentina","Daniela","Camila","Mariana","Sofía","Isabella","Paula","Carolina","Andrea","Natalia","Catalina","Juliana","Gabriela","Manuela","Sara","Alejandra","Elena","Diana","Lucía","Ximena","Adriana"]
    apellidos = ["Rodríguez","Gómez","Martínez","García","López","González","Pérez","Sánchez","Ramírez","Torres","Flores","Díaz","Restrepo","Jaramillo","Ospina","Bedoya","Gaviria","Morales","Herrera","Medina","Castro","Vargas","Ríos","Rojas","Ortiz","Silva","Luna","Mendoza","Cruz","Cárdenas","Mejía","Montoya"]
    dominios = ["gmail.com","outlook.com","hotmail.com","yahoo.com"]
    comidas = ["Estándar","Vegetariana","Vegana","Kosher","Halal","Sin Gluten"]
    prefs = ["Ventana","Pasillo","Medio","Cualquiera"]
    nacionalidades = ["Colombiana","Estadounidense","Española","Peruana","Mexicana","Argentina","Chilena"]
    pais_emisor_map = {"Colombiana":"Colombia","Estadounidense":"Estados Unidos","Española":"España","Peruana":"Perú","Mexicana":"México","Argentina":"Argentina","Chilena":"Chile"}

    pasajeros, documentos = [], []
    usados = set()
    datos_contacto = {}

    for i in range(1, cantidad+1):
        nombre = random.choice(masc if random.random()<0.5 else fem)
        ap1, ap2 = random.sample(apellidos, 2)
        full = f"{nombre} {ap1} {ap2}"
        nac = random.choices(nacionalidades, weights=[84,4,3,3,2,2,2])[0]
        fnac = date(1945,1,1) + timedelta(days=random.randint(0, int((date(2012,12,31)-date(1945,1,1)).days)))
        correo = None
        if random.random() > 0.08:
            correo = f"{ascii_simple(nombre).lower()}.{ascii_simple(ap1).lower()}{i}@{random.choice(dominios)}"
        tel = None if random.random() < 0.04 else f"+57 {random.choice([300,301,304,310,314,315,320])} {random.randint(1000000,9999999)}"
        comida = random.choices(comidas, weights=[84,6,2,2,2,4])[0]
        pref = random.choices(prefs, weights=[35,35,10,20])[0]
        pasajeros.append((i,full,correo,tel,fnac,nac,comida,pref))
        datos_contacto[i] = (correo,tel)

        edad_2025 = 2025 - fnac.year
        if nac == "Colombiana":
            if edad_2025 < 18:
                tipo = "Tarjeta de Identidad"
                num = str(random.randint(1000000000,1199999999))
                vence = None
            else:
                tipo = "Cédula de Ciudadanía"
                num = str(random.randint(1000000000,1199999999))
                vence = None
        else:
            tipo = "Pasaporte"
            num = "PA" + str(random.randint(10000000,99999999))
            vence = date(2027,1,1) + timedelta(days=random.randint(0, 8*365))
        pais = pais_emisor_map[nac]
        key = (tipo,num,pais)
        while key in usados:
            num = ("PA" + str(random.randint(10000000,99999999))) if tipo=="Pasaporte" else str(random.randint(1000000000,1199999999))
            key = (tipo,num,pais)
        usados.add(key)
        documentos.append((i,i,tipo,num,vence,pais))

    return pasajeros, documentos, datos_contacto


# ---------- Ventas, demanda, inventario y precios ----------

def ocupacion_objetivo(inf, fecha, estado):
    occ = inf["occ_base"] * factor_estacional(inf["tipo"], fecha.month)
    if inf["tipo"] == "troncal" and fecha.isoweekday() in (1,5):
        occ += 0.025
    if inf["tipo"] == "turistica" and fecha.isoweekday() in (5,6,7):
        occ += 0.035
    occ += random.uniform(-0.045, 0.045)
    if estado == "Cancelado":
        # Había reservas antes de la cancelación; no representa pasajeros transportados.
        occ *= random.uniform(0.55,0.80)
    return clamp(occ, 0.45, 0.96)


def construir_plan_ventas(vuelos_esp, info, cabinas_por_avion, asientos_por_avion_cabina):
    tarifa_por_cab = {1:[1,2,3,4],2:[5,6],3:[7,8,9],4:[10]}
    pesos_tarifa = {1:[0.18,0.30,0.32,0.20],2:[0.58,0.42],3:[0.40,0.35,0.25],4:[1.0]}
    ajuste_cab = {1:0.02,2:-0.025,3:-0.055,4:-0.10}

    plan = {}
    inventory_rows = []
    demand_rows = []
    price_rows = []
    price_map = {}
    id_inv = id_dem = id_price = 1

    for ve in vuelos_esp:
        id_esp,id_prog,id_avion,fv,estado,*_ = ve
        inf = info[id_prog]
        occ_global = ocupacion_objetivo(inf,fv,estado)
        cab_dist = cabinas_por_avion[id_avion]
        registros_venta = []
        total_reservas = 0
        total_cap = sum(cab_dist.values())

        for cab, cap_cab in sorted(cab_dist.items()):
            occ_cab = clamp(occ_global + ajuste_cab.get(cab,0), 0.30, 0.98)
            vendidos = min(cap_cab, max(0, round(cap_cab * occ_cab)))
            total_reservas += vendidos

            tarifas = tarifa_por_cab[cab]
            pesos = pesos_tarifa[cab]
            cupos = repartir_entero(cap_cab, pesos)
            ventas_tar = repartir_entero(vendidos, pesos)
            # Garantía local: ventas nunca superan bucket.
            exceso = 0
            for i in range(len(ventas_tar)):
                if ventas_tar[i] > cupos[i]:
                    exceso += ventas_tar[i] - cupos[i]
                    ventas_tar[i] = cupos[i]
            if exceso:
                for i in range(len(ventas_tar)):
                    libre = cupos[i] - ventas_tar[i]
                    take = min(libre, exceso)
                    ventas_tar[i] += take
                    exceso -= take
                    if exceso == 0:
                        break

            seats = list(asientos_por_avion_cabina[(id_avion,cab)])
            random.shuffle(seats)
            seat_cursor = 0
            for idx, tarifa in enumerate(tarifas):
                inv_ini = cupos[idx]
                sold = ventas_tar[idx]
                inventory_rows.append((id_inv,id_esp,tarifa,inv_ini,inv_ini-sold))
                id_inv += 1

                # Precio dinámico coherente con ruta, cabina, familia y estacionalidad.
                cab_mult = {1:1.0,2:1.75,3:3.6,4:7.2}[cab]
                fare_premium = {1:0.00,2:0.08,3:0.18,4:0.30,5:0.00,6:0.18,7:0.00,8:0.15,9:0.28,10:0.0}[tarifa]
                season = factor_estacional(inf["tipo"], fv.month)
                early = round(inf["precio_base"] * cab_mult * (1+fare_premium) * (0.92 + 0.08*season), -3)
                late = round(early * (1.12 + 0.20*occ_global), -3)
                fi1 = datetime.combine(fv - timedelta(days=60), time(0,0))
                ff1 = datetime.combine(fv - timedelta(days=15), time(23,59,59))
                fi2 = datetime.combine(fv - timedelta(days=14), time(0,0))
                price_rows.append((id_price,id_esp,tarifa,float(early),fi1,ff1,"Apertura de inventario / venta anticipada")); id_price += 1
                price_rows.append((id_price,id_esp,tarifa,float(late),fi2,None,"Ajuste dinámico por proximidad y ocupación")); id_price += 1
                price_map[(id_esp,tarifa)] = (float(early),float(late))

                for _ in range(sold):
                    seat_id = seats[seat_cursor]
                    seat_cursor += 1
                    registros_venta.append({"cabina":cab,"tarifa":tarifa,"asiento":seat_id})

        plan[id_esp] = {
            "ventas": registros_venta,
            "reservas_finales": total_reservas,
            "capacidad": total_cap,
            "occ": (total_reservas/total_cap if total_cap else 0),
        }

        # Curva de demanda: finaliza exactamente en las reservas del plan de ventas.
        final_res = total_reservas
        ratios = [
            random.uniform(0.36,0.52),
            random.uniform(0.61,0.74),
            random.uniform(0.80,0.90),
            random.uniform(0.96,1.00),
        ]
        valores = []
        prev = 0
        for ratio in ratios:
            v = min(final_res, max(prev, round(final_res*ratio)))
            valores.append(v); prev = v
        valores[-1] = final_res
        for dias_antes, reservas in zip([30,15,7,1], valores):
            fecha_h = datetime.combine(fv - timedelta(days=dias_antes), time(18,0))
            demand_rows.append((id_dem,id_esp,fecha_h,reservas,total_cap))
            id_dem += 1

    return plan, inventory_rows, price_rows, price_map, demand_rows


# ---------- PNR, segmentos y pagos ----------

def generar_pnr_segmentos_pagos(vuelos_esp, info, plan, price_map, pasajeros, datos_contacto):
    pnr_rows, seg_rows, pago_rows = [], [], []
    vuelo_map = {v[0]:v for v in vuelos_esp}
    passenger_ids = [p[0] for p in pasajeros]
    usados_pasajero_vuelo = defaultdict(set)
    codigos = set()
    id_pnr = id_seg = id_pago = 1

    # Grupos de reserva algo mayores para mantener el dataset compacto sin reducir los pasajeros transportados.
    tamanos = [1,2,3,4,5,6,7,8]
    pesos_tam = [1,3,6,10,20,25,20,15]
    canales = ["Web","App","Agencia","Call Center"]
    pesos_canales = [50,30,12,8]
    metodos = ["Tarjeta Crédito","Tarjeta Débito","PSE","Transferencia","Efectivo"]
    pesos_metodos = [42,15,30,10,3]

    for id_esp in sorted(plan):
        ventas = list(plan[id_esp]["ventas"])
        ve = vuelo_map[id_esp]
        _,id_prog,_,fv,estado,salida_real,_,_ = ve
        h_salida = info[id_prog]["hora_salida"]
        salida_prog = datetime.combine(fv,h_salida)
        random.shuffle(ventas)

        # Agrupar por cabina para evitar PNR familiares repartidos artificialmente entre clases.
        por_cab = defaultdict(list)
        for r in ventas:
            por_cab[r["cabina"]].append(r)

        for cab in sorted(por_cab):
            registros = por_cab[cab]
            i = 0
            while i < len(registros):
                tam = random.choices(tamanos, weights=pesos_tam, k=1)[0]
                grupo = registros[i:i+tam]
                i += len(grupo)
                if not grupo:
                    break

                # Código PNR único.
                chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
                while True:
                    codigo = "".join(random.choices(chars,k=6))
                    if codigo not in codigos:
                        codigos.add(codigo); break

                dias_antes = random.choices(
                    [random.randint(31,60), random.randint(15,30), random.randint(7,14), random.randint(2,6)],
                    weights=[22,36,27,15], k=1
                )[0]
                fecha_crea = datetime.combine(fv - timedelta(days=dias_antes), time(random.randint(6,22), random.randint(0,59)))

                if estado == "Cancelado":
                    estado_pnr = "Cancelada"
                    estado_pago = "Reembolsado"
                else:
                    estado_pnr = "Completada"
                    estado_pago = "Aprobado"

                # Elegir pasajeros distintos para este vuelo.
                elegidos = []
                disponibles = [p for p in passenger_ids if p not in usados_pasajero_vuelo[id_esp]]
                if len(disponibles) < len(grupo):
                    raise RuntimeError(f"No hay pasajeros suficientes para vuelo {id_esp}")
                elegidos = random.sample(disponibles, len(grupo))
                for p in elegidos:
                    usados_pasajero_vuelo[id_esp].add(p)

                contacto = elegidos[0]
                email,tel = datos_contacto[contacto]
                canal = random.choices(canales,weights=pesos_canales,k=1)[0]
                pnr_rows.append((id_pnr,codigo,fecha_crea,estado_pnr,email,tel,canal,"COP"))

                total_pago = 0.0
                for rec,pid in zip(grupo,elegidos):
                    tarifa = rec["tarifa"]
                    early,late = price_map[(id_esp,tarifa)]
                    precio = early if dias_antes >= 15 else late
                    # Dispersión comercial pequeña (promoción/cargo), siempre positiva.
                    precio = round(precio * random.uniform(0.97,1.05), -2)
                    total_pago += precio

                    if estado == "Cancelado":
                        estado_seg = "Cancelado"
                        checkin = abordaje = None
                    else:
                        no_show = random.random() < 0.025
                        if no_show:
                            estado_seg = "No Show"
                            checkin = abordaje = None
                        else:
                            estado_seg = "Volado"
                            base_salida = salida_real or salida_prog
                            checkin = max(fecha_crea, base_salida - timedelta(hours=random.randint(2,18), minutes=random.randint(0,59)))
                            abordaje = max(checkin, base_salida - timedelta(minutes=random.randint(25,45)))

                    seg_rows.append((
                        id_seg,id_pnr,pid,id_esp,tarifa,rec["asiento"],float(precio),
                        fecha_crea,checkin,abordaje,estado_seg
                    ))
                    id_seg += 1

                metodo = random.choices(metodos,weights=pesos_metodos,k=1)[0]
                fecha_pago = fecha_crea + timedelta(minutes=random.randint(2,40))
                referencia = f"TX{id_pago:08d}-{codigo}"
                pago_rows.append((id_pago,id_pnr,metodo,round(total_pago,2),fecha_pago,estado_pago,"COP",referencia))
                id_pago += 1
                id_pnr += 1

    return pnr_rows, seg_rows, pago_rows


# ---------- Validación interna ----------

def validar(aeropuertos,cabinas,aviones,distribuciones,asientos,vuelos_prog,dias_prog,vuelos_esp,demanda,tarifas,inventario,precios,reglas,pasajeros,documentos,pnrs,pagos,segmentos,plan,cabinas_por_avion):
    assert len({x[1] for x in aeropuertos}) == len(aeropuertos)
    assert len({x[1] for x in aviones}) == len(aviones)
    assert len({(x[1],x[3]) for x in asientos}) == len(asientos)
    assert len({(x[1],x[2]) for x in distribuciones}) == len(distribuciones)
    assert len({(x[1],x[2]) for x in dias_prog}) == len(dias_prog)
    assert len({(x[1],x[3]) for x in vuelos_esp}) == len(vuelos_esp)
    assert len({(x[1],x[2]) for x in demanda}) == len(demanda)
    assert len({(x[1],x[2]) for x in inventario}) == len(inventario)
    assert len({(x[1],x[2],x[4]) for x in precios}) == len(precios)
    assert len({x[1] for x in pnrs}) == len(pnrs)
    assert len({x[7] for x in pagos}) == len(pagos)
    assert len({(x[3],x[5]) for x in segmentos}) == len(segmentos)
    assert len({(x[1],x[2],x[3]) for x in segmentos}) == len(segmentos)

    # Demanda: 4 snapshots/flight, monotónica y final = plan de ventas.
    dem_por_v = defaultdict(list)
    for d in demanda:
        dem_por_v[d[1]].append(d)
    for idv, ds in dem_por_v.items():
        ds.sort(key=lambda x:x[2])
        vals = [x[3] for x in ds]
        assert len(ds) == 4
        assert vals == sorted(vals)
        assert vals[-1] == plan[idv]["reservas_finales"]
        assert all(x[3] <= x[4] for x in ds)

    # Capacidad física por avión = suma de cabinas.
    asientos_count = Counter(a[1] for a in asientos)
    for avion, dist in cabinas_por_avion.items():
        assert asientos_count[avion] == sum(dist.values())

    # Pagos = sumatoria de segmentos por PNR.
    suma_seg = defaultdict(float)
    for s in segmentos:
        suma_seg[s[1]] += s[6]
    for p in pagos:
        assert abs(p[3] - suma_seg[p[1]]) < 0.01

    # Ocupación final por ruta debe mostrar variabilidad real.
    vuelos_map = {v[0]:v for v in vuelos_esp}
    prog_map = {v[0]:v for v in vuelos_prog}
    rutas_occ = defaultdict(list)
    for idv,p in plan.items():
        ve = vuelos_map[idv]; vp = prog_map[ve[1]]
        ruta = (vp[2],vp[3])
        rutas_occ[ruta].append(p["occ"])
    proms = [sum(v)/len(v) for v in rutas_occ.values()]
    assert max(proms)-min(proms) > 0.12, "La ocupación por ruta quedó demasiado uniforme"


# ---------- Archivos ----------

def crear_maestro(archivos):
    ruta = os.path.join(OUTPUT_DIR,"datos_completos_v2.sql")
    with open(ruta,"w",encoding="utf-8") as out:
        out.write(f"USE {SCHEMA_NAME};\nSET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\nSET UNIQUE_CHECKS=0;\nSET AUTOCOMMIT=0;\nSTART TRANSACTION;\n\n")
        for nombre in archivos:
            with open(os.path.join(OUTPUT_DIR,nombre),"r",encoding="utf-8") as inp:
                for line in inp:
                    if line.startswith("USE ") or line.startswith("SET NAMES"):
                        continue
                    out.write(line)
                out.write("\n")
        out.write("COMMIT;\nSET UNIQUE_CHECKS=1;\nSET FOREIGN_KEY_CHECKS=1;\n")
    return ruta


def crear_validacion():
    ruta = os.path.join(OUTPUT_DIR,"validacion_v2.sql")
    sql = r'''USE aerolinea_db_v2;

-- 1. Conteos
SELECT 'aeropuerto' tabla, COUNT(*) registros FROM aeropuerto
UNION ALL SELECT 'avion', COUNT(*) FROM avion
UNION ALL SELECT 'cabina', COUNT(*) FROM cabina
UNION ALL SELECT 'avion_clase_asientos', COUNT(*) FROM avion_clase_asientos
UNION ALL SELECT 'asiento', COUNT(*) FROM asiento
UNION ALL SELECT 'vuelo_programado', COUNT(*) FROM vuelo_programado
UNION ALL SELECT 'vuelo_programado_dia', COUNT(*) FROM vuelo_programado_dia
UNION ALL SELECT 'vuelo_especifico', COUNT(*) FROM vuelo_especifico
UNION ALL SELECT 'demanda_vuelo', COUNT(*) FROM demanda_vuelo
UNION ALL SELECT 'tarifa', COUNT(*) FROM tarifa
UNION ALL SELECT 'inventario_tarifa', COUNT(*) FROM inventario_tarifa
UNION ALL SELECT 'precio_historico', COUNT(*) FROM precio_historico
UNION ALL SELECT 'regla_tarifa', COUNT(*) FROM regla_tarifa
UNION ALL SELECT 'pasajero', COUNT(*) FROM pasajero
UNION ALL SELECT 'documento_viaje', COUNT(*) FROM documento_viaje
UNION ALL SELECT 'reserva_pnr', COUNT(*) FROM reserva_pnr
UNION ALL SELECT 'pago', COUNT(*) FROM pago
UNION ALL SELECT 'segmento_vuelo', COUNT(*) FROM segmento_vuelo;

-- 2. Vuelos por ruta: deben ser diferentes
SELECT ruta, COUNT(*) total_vuelos
FROM vw_vuelos_analitica
GROUP BY ruta
ORDER BY total_vuelos DESC;

-- 3. Ocupación final media por ruta: debe mostrar diferencias claras
WITH final_demanda AS (
  SELECT d.*,
         ROW_NUMBER() OVER(PARTITION BY id_vuelo_especifico ORDER BY fecha_hora DESC) rn
  FROM demanda_vuelo d
)
SELECT v.ruta,
       COUNT(*) vuelos,
       ROUND(AVG(d.porcentaje_ocupacion),2) ocupacion_promedio
FROM final_demanda d
JOIN vw_vuelos_analitica v ON v.id_vuelo_especifico=d.id_vuelo_especifico
WHERE d.rn=1
GROUP BY v.ruta
ORDER BY ocupacion_promedio DESC;

-- 4. Evolución diaria (un mes de operación)
SELECT fecha_vuelo, COUNT(*) vuelos
FROM vuelo_especifico
GROUP BY fecha_vuelo
ORDER BY fecha_vuelo;

-- 5. Demanda monotónica (debe devolver 0)
WITH x AS (
 SELECT id_vuelo_especifico, fecha_hora, reservas_realizadas,
        LAG(reservas_realizadas) OVER(PARTITION BY id_vuelo_especifico ORDER BY fecha_hora) prev
 FROM demanda_vuelo
)
SELECT COUNT(*) inconsistencias_demanda
FROM x
WHERE prev IS NOT NULL AND reservas_realizadas < prev;

-- 6. Asiento/avión/cabina incompatibles (debe devolver 0)
SELECT COUNT(*) inconsistencias_asiento
FROM segmento_vuelo s
JOIN vuelo_especifico ve ON ve.id_vuelo_especifico=s.id_vuelo_especifico
JOIN asiento a ON a.id_asiento=s.id_asiento
JOIN tarifa t ON t.id_tarifa=s.id_tarifa
WHERE a.id_avion<>ve.id_avion_asignado OR a.id_cabina<>t.id_cabina;

-- 7. Pago vs segmentos (debe devolver 0)
SELECT COUNT(*) inconsistencias_pago
FROM pago p
JOIN (
 SELECT id_pnr, ROUND(SUM(precio_final_pagado),2) total_segmentos
 FROM segmento_vuelo GROUP BY id_pnr
) s ON s.id_pnr=p.id_pnr
WHERE ABS(p.monto_total-s.total_segmentos)>0.01;
'''
    with open(ruta,"w",encoding="utf-8") as f:
        f.write(sql)
    return ruta


def main():
    print("===============================================================")
    print(" GENERANDO AEROLINEA_DB_V2 - 1 MES / PERFIL COMPACTO REALISTA")
    print("===============================================================")
    os.makedirs(OUTPUT_DIR,exist_ok=True)

    aeropuertos,mapa_aer = generar_aeropuertos()
    cabinas = generar_cabinas()
    aviones,distribuciones,asientos,asientos_por_avion_cabina,capacidad_por_avion,cabinas_por_avion,avion_por_modelo = generar_flota_y_asientos()
    tarifas,reglas = generar_tarifas_reglas()
    vuelos_prog,dias_prog,info = generar_programacion(mapa_aer)
    vuelos_esp = generar_vuelos_especificos(vuelos_prog,info,avion_por_modelo)
    pasajeros,documentos,datos_contacto = generar_pasajeros_documentos(NUM_PASAJEROS)
    plan,inventario,precios,price_map,demanda = construir_plan_ventas(vuelos_esp,info,cabinas_por_avion,asientos_por_avion_cabina)
    pnrs,segmentos,pagos = generar_pnr_segmentos_pagos(vuelos_esp,info,plan,price_map,pasajeros,datos_contacto)

    validar(aeropuertos,cabinas,aviones,distribuciones,asientos,vuelos_prog,dias_prog,vuelos_esp,demanda,tarifas,inventario,precios,reglas,pasajeros,documentos,pnrs,pagos,segmentos,plan,cabinas_por_avion)

    specs = [
        ("01_aeropuerto.sql","aeropuerto",["id_aeropuerto","codigo_iata","nombre_aeropuerto","ciudad","pais","zona_horaria"],aeropuertos),
        ("02_cabina.sql","cabina",["id_cabina","codigo_cabina","nombre_cabina","descripcion"],cabinas),
        ("03_avion.sql","avion",["id_avion","matricula","modelo","capacidad_total","estado"],aviones),
        ("04_avion_clase_asientos.sql","avion_clase_asientos",["id_distribucion","id_avion","id_cabina","cantidad_asientos"],distribuciones),
        ("05_asiento.sql","asiento",["id_asiento","id_avion","id_cabina","codigo_asiento","fila","letra","ubicacion"],asientos),
        ("06_vuelo_programado.sql","vuelo_programado",["id_vuelo_programado","numero_vuelo","id_aeropuerto_origen","id_aeropuerto_destino","hora_salida","hora_llegada","dias_llegada","vigente_desde","vigente_hasta","activo"],vuelos_prog),
        ("07_vuelo_programado_dia.sql","vuelo_programado_dia",["id_vuelo_dia","id_vuelo_programado","dia_semana","nombre_dia"],dias_prog),
        ("08_vuelo_especifico.sql","vuelo_especifico",["id_vuelo_especifico","id_vuelo_programado","id_avion_asignado","fecha_vuelo","estado","salida_real","llegada_real","motivo_irregularidad"],vuelos_esp),
        ("09_tarifa.sql","tarifa",["id_tarifa","codigo_tarifa","id_cabina","permite_cambios","permite_reembolsos"],tarifas),
        ("10_regla_tarifa.sql","regla_tarifa",["id_regla","id_tarifa","tipo_regla","valor_monetario","descripcion"],reglas),
        ("11_inventario_tarifa.sql","inventario_tarifa",["id_inventario","id_vuelo_especifico","id_tarifa","cupos_iniciales","cupos_disponibles"],inventario),
        ("12_precio_historico.sql","precio_historico",["id_precio","id_vuelo_especifico","id_tarifa","precio","fecha_inicio","fecha_fin","motivo_cambio"],precios),
        ("13_pasajero.sql","pasajero",["id_pasajero","nombre_completo","email","telefono","fecha_nacimiento","nacionalidad","preferencia_comida","preferencia_asiento"],pasajeros),
        ("14_documento_viaje.sql","documento_viaje",["id_documento","id_pasajero","tipo_documento","numero_documento","fecha_vencimiento","pais_emisor"],documentos),
        ("15_reserva_pnr.sql","reserva_pnr",["id_pnr","codigo_pnr","fecha_creacion","estado","email_contacto","telefono_contacto","canal_venta","moneda"],pnrs),
        ("16_pago.sql","pago",["id_pago","id_pnr","metodo_pago","monto_total","fecha","estado","moneda","referencia_transaccion"],pagos),
        ("17_segmento_vuelo.sql","segmento_vuelo",["id_segmento","id_pnr","id_pasajero","id_vuelo_especifico","id_tarifa","id_asiento","precio_final_pagado","fecha_reserva","fecha_checkin","fecha_abordaje","estado_segmento"],segmentos),
        ("18_demanda_vuelo.sql","demanda_vuelo",["id_demanda","id_vuelo_especifico","fecha_hora","reservas_realizadas","capacidad_ofertada"],demanda),
    ]

    archivos = []
    for nombre,tabla,cols,filas in specs:
        escribir_sql(nombre,tabla,cols,filas)
        archivos.append(nombre)

    maestro = crear_maestro(archivos)
    validacion = crear_validacion()

    conteos = [(tabla,len(filas)) for _,tabla,_,filas in specs]
    total = sum(n for _,n in conteos)
    print("\nRESUMEN")
    for tabla,n in conteos:
        print(f"  {tabla:<25} {n:>7,}")
    print("  " + "-"*34)
    print(f"  {'TOTAL':<25} {total:>7,}")
    print(f"\nMaestro: {maestro}")
    print(f"Validación: {validacion}")

    # Indicadores rápidos para confirmar que no quedó plano.
    vuelos_por_prog = Counter(v[1] for v in vuelos_esp)
    print(f"\nVuelos específicos: min/programa={min(vuelos_por_prog.values())}, max/programa={max(vuelos_por_prog.values())}")
    occs = [p['occ'] for p in plan.values()]
    print(f"Ocupación final por vuelo: min={min(occs)*100:.1f}% | prom={sum(occs)/len(occs)*100:.1f}% | max={max(occs)*100:.1f}%")


if __name__ == "__main__":
    main()
