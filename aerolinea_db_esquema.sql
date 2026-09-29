-- ============================================================
-- AEROLINEA_DB V2 - ESQUEMA CORREGIDO Y COMPATIBLE CON POWER BI
-- Mantiene las tablas/columnas usadas por el PBIX actual y agrega
-- mejoras de integridad sin modificar aerolinea_db (V1).
-- MySQL 8+ / InnoDB / utf8mb4
-- ============================================================

DROP DATABASE IF EXISTS aerolinea_db_v2;
CREATE DATABASE aerolinea_db_v2
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE aerolinea_db_v2;

-- ============================================================
-- 1. MAESTROS
-- ============================================================

CREATE TABLE aeropuerto (
    id_aeropuerto INT NOT NULL AUTO_INCREMENT,
    codigo_iata CHAR(3) NOT NULL,
    nombre_aeropuerto VARCHAR(150) NOT NULL,
    ciudad VARCHAR(100) NOT NULL,
    pais VARCHAR(80) NOT NULL,
    -- Campo nuevo; las cinco columnas anteriores permanecen intactas.
    zona_horaria VARCHAR(64) NOT NULL,
    PRIMARY KEY (id_aeropuerto),
    UNIQUE KEY uq_aeropuerto_iata (codigo_iata)
) ENGINE=InnoDB;

CREATE TABLE cabina (
    id_cabina INT NOT NULL AUTO_INCREMENT,
    codigo_cabina VARCHAR(5) NOT NULL,
    nombre_cabina VARCHAR(50) NOT NULL,
    descripcion VARCHAR(200) NULL,
    PRIMARY KEY (id_cabina),
    UNIQUE KEY uq_cabina_codigo (codigo_cabina),
    UNIQUE KEY uq_cabina_nombre (nombre_cabina)
) ENGINE=InnoDB;

CREATE TABLE avion (
    id_avion INT NOT NULL AUTO_INCREMENT,
    matricula VARCHAR(20) NOT NULL,
    modelo VARCHAR(50) NOT NULL,
    -- Se conserva porque el modelo de Power BI actual la utiliza.
    capacidad_total INT NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'Activo',
    PRIMARY KEY (id_avion),
    UNIQUE KEY uq_avion_matricula (matricula),
    CONSTRAINT chk_avion_capacidad CHECK (capacidad_total > 0),
    CONSTRAINT chk_avion_estado
      CHECK (estado IN ('Activo','Mantenimiento','Fuera de Servicio'))
) ENGINE=InnoDB;

-- Se conserva el nombre y las columnas originales para no romper Power BI.
CREATE TABLE avion_clase_asientos (
    id_distribucion INT NOT NULL AUTO_INCREMENT,
    id_avion INT NOT NULL,
    id_cabina INT NOT NULL,
    cantidad_asientos INT NOT NULL,
    PRIMARY KEY (id_distribucion),
    UNIQUE KEY uq_avion_cabina (id_avion,id_cabina),
    KEY ix_distrib_cabina (id_cabina),
    CONSTRAINT fk_distrib_avion
      FOREIGN KEY (id_avion) REFERENCES avion(id_avion) ON DELETE CASCADE,
    CONSTRAINT fk_distrib_cabina
      FOREIGN KEY (id_cabina) REFERENCES cabina(id_cabina),
    CONSTRAINT chk_distrib_cantidad CHECK (cantidad_asientos > 0)
) ENGINE=InnoDB;

CREATE TABLE asiento (
    id_asiento INT NOT NULL AUTO_INCREMENT,
    id_avion INT NOT NULL,
    id_cabina INT NOT NULL,
    codigo_asiento VARCHAR(10) NOT NULL,
    fila INT NOT NULL,
    letra CHAR(1) NOT NULL,
    ubicacion VARCHAR(20) NOT NULL,
    PRIMARY KEY (id_asiento),
    UNIQUE KEY uq_avion_asiento (id_avion,codigo_asiento),
    KEY ix_asiento_cabina (id_cabina),
    KEY ix_asiento_avion_cabina (id_avion,id_cabina),
    CONSTRAINT fk_asiento_avion
      FOREIGN KEY (id_avion) REFERENCES avion(id_avion) ON DELETE CASCADE,
    CONSTRAINT fk_asiento_cabina
      FOREIGN KEY (id_cabina) REFERENCES cabina(id_cabina),
    CONSTRAINT fk_asiento_avion_cabina
      FOREIGN KEY (id_avion,id_cabina)
      REFERENCES avion_clase_asientos(id_avion,id_cabina),
    CONSTRAINT chk_asiento_fila CHECK (fila > 0),
    CONSTRAINT chk_asiento_ubicacion
      CHECK (ubicacion IN ('Ventana','Medio','Pasillo'))
) ENGINE=InnoDB;

-- ============================================================
-- 2. PROGRAMACIÓN Y OPERACIÓN
-- ============================================================

CREATE TABLE vuelo_programado (
    id_vuelo_programado INT NOT NULL AUTO_INCREMENT,
    numero_vuelo VARCHAR(10) NOT NULL,
    id_aeropuerto_origen INT NOT NULL,
    id_aeropuerto_destino INT NOT NULL,
    hora_salida TIME NOT NULL,
    hora_llegada TIME NOT NULL,
    -- Campos nuevos después de las columnas originales.
    dias_llegada TINYINT NOT NULL DEFAULT 0,
    vigente_desde DATE NOT NULL,
    vigente_hasta DATE NOT NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (id_vuelo_programado),
    UNIQUE KEY uq_vuelo_programado_version (numero_vuelo,vigente_desde),
    KEY ix_vuelo_origen (id_aeropuerto_origen),
    KEY ix_vuelo_destino (id_aeropuerto_destino),
    CONSTRAINT fk_vuelo_orig
      FOREIGN KEY (id_aeropuerto_origen) REFERENCES aeropuerto(id_aeropuerto),
    CONSTRAINT fk_vuelo_dest
      FOREIGN KEY (id_aeropuerto_destino) REFERENCES aeropuerto(id_aeropuerto),
    CONSTRAINT chk_aeropuertos_distintos
      CHECK (id_aeropuerto_origen <> id_aeropuerto_destino),
    CONSTRAINT chk_vuelo_dias_llegada CHECK (dias_llegada BETWEEN 0 AND 2),
    CONSTRAINT chk_vuelo_vigencia CHECK (vigente_hasta >= vigente_desde)
) ENGINE=InnoDB;

-- Se conservan id_vuelo_dia y nombre_dia por compatibilidad con la consulta
-- existente (aunque actualmente tenga carga deshabilitada en Power BI).
CREATE TABLE vuelo_programado_dia (
    id_vuelo_dia INT NOT NULL AUTO_INCREMENT,
    id_vuelo_programado INT NOT NULL,
    dia_semana TINYINT NOT NULL,
    nombre_dia VARCHAR(15) NOT NULL,
    PRIMARY KEY (id_vuelo_dia),
    UNIQUE KEY uq_vuelo_dia (id_vuelo_programado,dia_semana),
    CONSTRAINT fk_vuelo_dia_prog
      FOREIGN KEY (id_vuelo_programado)
      REFERENCES vuelo_programado(id_vuelo_programado) ON DELETE CASCADE,
    CONSTRAINT chk_dia_semana CHECK (dia_semana BETWEEN 1 AND 7),
    CONSTRAINT chk_nombre_dia CHECK (
      (dia_semana=1 AND nombre_dia='Lunes') OR
      (dia_semana=2 AND nombre_dia='Martes') OR
      (dia_semana=3 AND nombre_dia='Miércoles') OR
      (dia_semana=4 AND nombre_dia='Jueves') OR
      (dia_semana=5 AND nombre_dia='Viernes') OR
      (dia_semana=6 AND nombre_dia='Sábado') OR
      (dia_semana=7 AND nombre_dia='Domingo')
    )
) ENGINE=InnoDB;

CREATE TABLE vuelo_especifico (
    id_vuelo_especifico INT NOT NULL AUTO_INCREMENT,
    id_vuelo_programado INT NOT NULL,
    id_avion_asignado INT NOT NULL,
    fecha_vuelo DATE NOT NULL,
    estado VARCHAR(30) NOT NULL DEFAULT 'Programado',
    -- Nuevos datos operacionales; no interfieren con las cinco columnas originales.
    salida_real DATETIME NULL,
    llegada_real DATETIME NULL,
    motivo_irregularidad VARCHAR(150) NULL,
    PRIMARY KEY (id_vuelo_especifico),
    UNIQUE KEY uq_vuelo_fecha (id_vuelo_programado,fecha_vuelo),
    KEY ix_vuelo_esp_avion (id_avion_asignado),
    KEY ix_vuelo_esp_fecha (fecha_vuelo),
    KEY ix_vuelo_esp_estado (estado),
    CONSTRAINT fk_vuelo_esp_avion
      FOREIGN KEY (id_avion_asignado) REFERENCES avion(id_avion),
    CONSTRAINT fk_vuelo_esp_prog
      FOREIGN KEY (id_vuelo_programado) REFERENCES vuelo_programado(id_vuelo_programado),
    CONSTRAINT chk_vuelo_estado CHECK (estado IN
      ('Programado','Abordando','En Vuelo','Realizado','Cancelado','Demorado','Desviado')),
    CONSTRAINT chk_vuelo_horas_reales
      CHECK (llegada_real IS NULL OR salida_real IS NULL OR llegada_real >= salida_real)
) ENGINE=InnoDB;

-- ============================================================
-- 3. TARIFAS, INVENTARIO Y PRECIOS
-- ============================================================

CREATE TABLE tarifa (
    id_tarifa INT NOT NULL AUTO_INCREMENT,
    codigo_tarifa VARCHAR(10) NOT NULL,
    id_cabina INT NOT NULL,
    permite_cambios TINYINT(1) NOT NULL DEFAULT 0,
    permite_reembolsos TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY (id_tarifa),
    UNIQUE KEY uq_tarifa_codigo (codigo_tarifa),
    KEY ix_tarifa_cabina (id_cabina),
    CONSTRAINT fk_tarifa_cabina
      FOREIGN KEY (id_cabina) REFERENCES cabina(id_cabina)
) ENGINE=InnoDB;

CREATE TABLE regla_tarifa (
    id_regla INT NOT NULL AUTO_INCREMENT,
    id_tarifa INT NOT NULL,
    tipo_regla VARCHAR(80) NOT NULL,
    valor_monetario DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    descripcion VARCHAR(255) NULL,
    PRIMARY KEY (id_regla),
    UNIQUE KEY uq_regla_tarifa_tipo (id_tarifa,tipo_regla),
    CONSTRAINT fk_regla_tarifa
      FOREIGN KEY (id_tarifa) REFERENCES tarifa(id_tarifa) ON DELETE CASCADE,
    CONSTRAINT chk_regla_valor CHECK (valor_monetario >= 0)
) ENGINE=InnoDB;

CREATE TABLE inventario_tarifa (
    id_inventario INT NOT NULL AUTO_INCREMENT,
    id_vuelo_especifico INT NOT NULL,
    id_tarifa INT NOT NULL,
    cupos_iniciales INT NOT NULL,
    cupos_disponibles INT NOT NULL,
    PRIMARY KEY (id_inventario),
    UNIQUE KEY uq_inventario_vuelo_tarifa (id_vuelo_especifico,id_tarifa),
    KEY ix_inventario_tarifa (id_tarifa),
    CONSTRAINT fk_inventario_vuelo
      FOREIGN KEY (id_vuelo_especifico) REFERENCES vuelo_especifico(id_vuelo_especifico) ON DELETE CASCADE,
    CONSTRAINT fk_inventario_tarifa
      FOREIGN KEY (id_tarifa) REFERENCES tarifa(id_tarifa),
    CONSTRAINT chk_inventario_inicial CHECK (cupos_iniciales >= 0),
    CONSTRAINT chk_inventario_disponible
      CHECK (cupos_disponibles >= 0 AND cupos_disponibles <= cupos_iniciales)
) ENGINE=InnoDB;

CREATE TABLE precio_historico (
    id_precio INT NOT NULL AUTO_INCREMENT,
    id_vuelo_especifico INT NOT NULL,
    id_tarifa INT NOT NULL,
    precio DECIMAL(12,2) NOT NULL,
    fecha_inicio DATETIME NOT NULL,
    fecha_fin DATETIME NULL,
    motivo_cambio VARCHAR(150) NULL,
    PRIMARY KEY (id_precio),
    UNIQUE KEY uq_precio_inicio (id_vuelo_especifico,id_tarifa,fecha_inicio),
    KEY ix_precio_tarifa (id_tarifa),
    KEY ix_precio_vuelo (id_vuelo_especifico),
    CONSTRAINT fk_precio_tarifa
      FOREIGN KEY (id_tarifa) REFERENCES tarifa(id_tarifa),
    CONSTRAINT fk_precio_vuelo
      FOREIGN KEY (id_vuelo_especifico) REFERENCES vuelo_especifico(id_vuelo_especifico) ON DELETE CASCADE,
    CONSTRAINT chk_precio_no_negativo CHECK (precio >= 0),
    CONSTRAINT chk_precio_intervalo CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio)
) ENGINE=InnoDB;

-- ============================================================
-- 4. PASAJEROS, RESERVAS Y PAGOS
-- ============================================================

CREATE TABLE pasajero (
    id_pasajero INT NOT NULL AUTO_INCREMENT,
    nombre_completo VARCHAR(150) NOT NULL,
    email VARCHAR(150) NULL,
    telefono VARCHAR(30) NULL,
    preferencia_comida VARCHAR(40) NULL,
    preferencia_asiento VARCHAR(20) NULL,
    -- Campos nuevos al final para preservar la forma original.
    fecha_nacimiento DATE NULL,
    nacionalidad VARCHAR(80) NULL,
    PRIMARY KEY (id_pasajero),
    KEY ix_pasajero_email (email),
    CONSTRAINT chk_pasajero_preferencia_asiento CHECK (
      preferencia_asiento IS NULL OR preferencia_asiento IN ('Ventana','Medio','Pasillo','Cualquiera')
    )
) ENGINE=InnoDB;

CREATE TABLE documento_viaje (
    id_documento INT NOT NULL AUTO_INCREMENT,
    id_pasajero INT NOT NULL,
    tipo_documento VARCHAR(30) NOT NULL,
    numero_documento VARCHAR(50) NOT NULL,
    fecha_vencimiento DATE NULL,
    pais_emisor VARCHAR(80) NOT NULL,
    PRIMARY KEY (id_documento),
    UNIQUE KEY uq_pasajero_doc (tipo_documento,numero_documento,pais_emisor),
    KEY ix_doc_pasajero (id_pasajero),
    CONSTRAINT fk_doc_pasajero
      FOREIGN KEY (id_pasajero) REFERENCES pasajero(id_pasajero) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE reserva_pnr (
    id_pnr INT NOT NULL AUTO_INCREMENT,
    codigo_pnr CHAR(6) NOT NULL,
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(30) NOT NULL DEFAULT 'Pendiente de Pago',
    email_contacto VARCHAR(150) NULL,
    telefono_contacto VARCHAR(30) NULL,
    canal_venta VARCHAR(20) NOT NULL DEFAULT 'Web',
    moneda CHAR(3) NOT NULL DEFAULT 'COP',
    PRIMARY KEY (id_pnr),
    UNIQUE KEY uq_reserva_codigo_pnr (codigo_pnr),
    KEY ix_reserva_fecha (fecha_creacion),
    KEY ix_reserva_estado (estado),
    CONSTRAINT chk_reserva_estado
      CHECK (estado IN ('Pendiente de Pago','Confirmada','Cancelada','Completada')),
    CONSTRAINT chk_reserva_canal
      CHECK (canal_venta IN ('Web','App','Agencia','Call Center'))
) ENGINE=InnoDB;

CREATE TABLE segmento_vuelo (
    id_segmento INT NOT NULL AUTO_INCREMENT,
    id_pnr INT NOT NULL,
    id_pasajero INT NOT NULL,
    id_vuelo_especifico INT NOT NULL,
    id_tarifa INT NOT NULL,
    id_asiento INT NULL,
    precio_final_pagado DECIMAL(12,2) NOT NULL,
    fecha_reserva DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_checkin DATETIME NULL,
    fecha_abordaje DATETIME NULL,
    estado_segmento VARCHAR(30) NOT NULL DEFAULT 'Emitido',
    PRIMARY KEY (id_segmento),
    UNIQUE KEY uq_vuelo_asiento (id_vuelo_especifico,id_asiento),
    UNIQUE KEY uq_segmento_pasajero_vuelo (id_pnr,id_pasajero,id_vuelo_especifico),
    KEY ix_seg_pnr (id_pnr),
    KEY ix_seg_pasajero (id_pasajero),
    KEY ix_seg_vuelo (id_vuelo_especifico),
    KEY ix_seg_tarifa (id_tarifa),
    KEY ix_seg_asiento (id_asiento),
    KEY ix_seg_fecha_reserva (fecha_reserva),
    CONSTRAINT fk_seg_pnr
      FOREIGN KEY (id_pnr) REFERENCES reserva_pnr(id_pnr) ON DELETE CASCADE,
    CONSTRAINT fk_seg_pasajero
      FOREIGN KEY (id_pasajero) REFERENCES pasajero(id_pasajero),
    CONSTRAINT fk_seg_vuelo_esp
      FOREIGN KEY (id_vuelo_especifico) REFERENCES vuelo_especifico(id_vuelo_especifico),
    CONSTRAINT fk_seg_tarifa
      FOREIGN KEY (id_tarifa) REFERENCES tarifa(id_tarifa),
    CONSTRAINT fk_seg_asiento
      FOREIGN KEY (id_asiento) REFERENCES asiento(id_asiento),
    CONSTRAINT chk_seg_precio CHECK (precio_final_pagado >= 0),
    CONSTRAINT chk_seg_estado CHECK (estado_segmento IN
      ('Emitido','Check-in','Abordado','Volado','Cancelado','No Show')),
    CONSTRAINT chk_seg_fechas CHECK (
      (fecha_checkin IS NULL OR fecha_checkin >= fecha_reserva) AND
      (fecha_abordaje IS NULL OR fecha_checkin IS NULL OR fecha_abordaje >= fecha_checkin)
    )
) ENGINE=InnoDB;

CREATE TABLE pago (
    id_pago INT NOT NULL AUTO_INCREMENT,
    id_pnr INT NOT NULL,
    metodo_pago VARCHAR(30) NOT NULL,
    monto_total DECIMAL(12,2) NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) NOT NULL DEFAULT 'Aprobado',
    moneda CHAR(3) NOT NULL DEFAULT 'COP',
    referencia_transaccion VARCHAR(50) NULL,
    PRIMARY KEY (id_pago),
    UNIQUE KEY uq_pago_referencia (referencia_transaccion),
    KEY ix_pago_pnr (id_pnr),
    KEY ix_pago_fecha (fecha),
    CONSTRAINT fk_pago_pnr
      FOREIGN KEY (id_pnr) REFERENCES reserva_pnr(id_pnr),
    CONSTRAINT chk_pago_monto CHECK (monto_total >= 0),
    CONSTRAINT chk_pago_metodo CHECK (metodo_pago IN
      ('Tarjeta Crédito','Tarjeta Débito','PSE','Transferencia','Efectivo')),
    CONSTRAINT chk_pago_estado CHECK (estado IN
      ('Aprobado','Pendiente','Rechazado','Reembolsado'))
) ENGINE=InnoDB;

-- ============================================================
-- 5. DEMANDA HISTÓRICA
-- ============================================================

CREATE TABLE demanda_vuelo (
    id_demanda INT NOT NULL AUTO_INCREMENT,
    id_vuelo_especifico INT NOT NULL,
    fecha_hora DATETIME NOT NULL,
    reservas_realizadas INT NOT NULL DEFAULT 0,
    -- Se conserva el nombre porcentaje_ocupacion que ya utiliza Power BI,
    -- pero ahora MySQL lo calcula a partir de una capacidad histórica guardada.
    porcentaje_ocupacion DECIMAL(5,2)
      GENERATED ALWAYS AS (
        CASE WHEN capacidad_ofertada > 0
             THEN ROUND((reservas_realizadas * 100.0) / capacidad_ofertada,2)
             ELSE 0 END
      ) STORED,
    capacidad_ofertada INT NOT NULL,
    PRIMARY KEY (id_demanda),
    UNIQUE KEY uq_demanda_vuelo_momento (id_vuelo_especifico,fecha_hora),
    KEY ix_demanda_fecha (fecha_hora),
    CONSTRAINT fk_demanda_vuelo
      FOREIGN KEY (id_vuelo_especifico) REFERENCES vuelo_especifico(id_vuelo_especifico) ON DELETE CASCADE,
    CONSTRAINT chk_demanda_reservas CHECK (reservas_realizadas >= 0),
    CONSTRAINT chk_demanda_capacidad CHECK (capacidad_ofertada > 0),
    CONSTRAINT chk_demanda_limite CHECK (reservas_realizadas <= capacidad_ofertada)
) ENGINE=InnoDB;

-- ============================================================
-- 6. INTEGRIDAD CRUZADA DE SEGMENTO / AVIÓN / CABINA / ASIENTO
-- ============================================================

DELIMITER $$
CREATE TRIGGER trg_segmento_validar_asiento_bi
BEFORE INSERT ON segmento_vuelo
FOR EACH ROW
BEGIN
    DECLARE v_avion INT;
    DECLARE v_cabina_tarifa INT;
    DECLARE v_asiento_avion INT;
    DECLARE v_asiento_cabina INT;

    SELECT id_avion_asignado INTO v_avion
      FROM vuelo_especifico
     WHERE id_vuelo_especifico=NEW.id_vuelo_especifico;

    SELECT id_cabina INTO v_cabina_tarifa
      FROM tarifa
     WHERE id_tarifa=NEW.id_tarifa;

    IF NOT EXISTS (
      SELECT 1 FROM avion_clase_asientos
       WHERE id_avion=v_avion AND id_cabina=v_cabina_tarifa
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT='La tarifa pertenece a una cabina inexistente en el avión asignado';
    END IF;

    IF NEW.id_asiento IS NOT NULL THEN
      SELECT id_avion,id_cabina INTO v_asiento_avion,v_asiento_cabina
        FROM asiento WHERE id_asiento=NEW.id_asiento;
      IF v_asiento_avion<>v_avion THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT='El asiento no pertenece al avión asignado al vuelo';
      END IF;
      IF v_asiento_cabina<>v_cabina_tarifa THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT='El asiento no pertenece a la cabina de la tarifa';
      END IF;
    END IF;
END$$

CREATE TRIGGER trg_segmento_validar_asiento_bu
BEFORE UPDATE ON segmento_vuelo
FOR EACH ROW
BEGIN
    DECLARE v_avion INT;
    DECLARE v_cabina_tarifa INT;
    DECLARE v_asiento_avion INT;
    DECLARE v_asiento_cabina INT;

    SELECT id_avion_asignado INTO v_avion
      FROM vuelo_especifico
     WHERE id_vuelo_especifico=NEW.id_vuelo_especifico;
    SELECT id_cabina INTO v_cabina_tarifa
      FROM tarifa WHERE id_tarifa=NEW.id_tarifa;

    IF NOT EXISTS (
      SELECT 1 FROM avion_clase_asientos
       WHERE id_avion=v_avion AND id_cabina=v_cabina_tarifa
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT='La tarifa pertenece a una cabina inexistente en el avión asignado';
    END IF;

    IF NEW.id_asiento IS NOT NULL THEN
      SELECT id_avion,id_cabina INTO v_asiento_avion,v_asiento_cabina
        FROM asiento WHERE id_asiento=NEW.id_asiento;
      IF v_asiento_avion<>v_avion THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT='El asiento no pertenece al avión asignado al vuelo';
      END IF;
      IF v_asiento_cabina<>v_cabina_tarifa THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT='El asiento no pertenece a la cabina de la tarifa';
      END IF;
    END IF;
END$$
DELIMITER ;

-- ============================================================
-- 7. VISTAS ANALÍTICAS ADICIONALES (opcionales para Power BI)
-- ============================================================

CREATE OR REPLACE VIEW vw_vuelos_analitica AS
SELECT
    ve.id_vuelo_especifico,
    vp.numero_vuelo,
    ve.fecha_vuelo,
    ve.estado,
    ve.id_avion_asignado,
    av.matricula,
    av.modelo,
    av.capacidad_total,
    ori.codigo_iata AS origen_iata,
    ori.ciudad AS origen_ciudad,
    ori.pais AS origen_pais,
    des.codigo_iata AS destino_iata,
    des.ciudad AS destino_ciudad,
    des.pais AS destino_pais,
    CONCAT(ori.codigo_iata,' → ',des.codigo_iata) AS ruta,
    vp.hora_salida,
    vp.hora_llegada,
    vp.dias_llegada,
    ve.salida_real,
    ve.llegada_real
FROM vuelo_especifico ve
JOIN vuelo_programado vp ON vp.id_vuelo_programado=ve.id_vuelo_programado
JOIN avion av ON av.id_avion=ve.id_avion_asignado
JOIN aeropuerto ori ON ori.id_aeropuerto=vp.id_aeropuerto_origen
JOIN aeropuerto des ON des.id_aeropuerto=vp.id_aeropuerto_destino;

CREATE OR REPLACE VIEW vw_demanda_analitica AS
SELECT
    d.id_demanda,
    d.id_vuelo_especifico,
    d.fecha_hora,
    d.reservas_realizadas,
    d.porcentaje_ocupacion,
    d.capacidad_ofertada,
    ve.fecha_vuelo,
    DATEDIFF(ve.fecha_vuelo,DATE(d.fecha_hora)) AS dias_antes_vuelo
FROM demanda_vuelo d
JOIN vuelo_especifico ve ON ve.id_vuelo_especifico=d.id_vuelo_especifico;

CREATE OR REPLACE VIEW vw_segmentos_analitica AS
SELECT
    s.*,
    t.id_cabina,
    c.codigo_cabina,
    c.nombre_cabina
FROM segmento_vuelo s
JOIN tarifa t ON t.id_tarifa=s.id_tarifa
JOIN cabina c ON c.id_cabina=t.id_cabina;
