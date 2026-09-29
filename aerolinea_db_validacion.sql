USE aerolinea_db_v2;

-- IMPORTANTE: Workbench 26.7 puede visualizar valores DATE con un desfase de zona horaria
-- en la cuadrícula. DATE_FORMAT fuerza a mostrarlos como texto y permite verificar
-- el valor realmente almacenado en MySQL.

-- 0. Verificación exacta del rango almacenado
SELECT DATE_FORMAT(MIN(fecha_vuelo), '%Y-%m-%d') AS primera_fecha_real,
       DATE_FORMAT(MAX(fecha_vuelo), '%Y-%m-%d') AS ultima_fecha_real,
       COUNT(DISTINCT fecha_vuelo) AS dias_con_vuelos
FROM vuelo_especifico;


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

-- 4. Evolución diaria: debe mostrar actividad durante todo noviembre
SELECT DATE_FORMAT(fecha_vuelo, '%Y-%m-%d') AS fecha_vuelo, COUNT(*) AS vuelos
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

-- 8. Capacidad declarada vs asientos físicos (debe devolver 0)
SELECT COUNT(*) inconsistencias_capacidad
FROM avion av
JOIN (
  SELECT id_avion, COUNT(*) capacidad_fisica
  FROM asiento
  GROUP BY id_avion
) x ON x.id_avion=av.id_avion
WHERE av.capacidad_total<>x.capacidad_fisica;

-- 9. Distribución por cabina vs asientos físicos (debe devolver 0)
SELECT COUNT(*) inconsistencias_distribucion
FROM avion_clase_asientos ac
LEFT JOIN (
  SELECT id_avion,id_cabina,COUNT(*) cantidad_fisica
  FROM asiento
  GROUP BY id_avion,id_cabina
) x ON x.id_avion=ac.id_avion AND x.id_cabina=ac.id_cabina
WHERE ac.cantidad_asientos<>COALESCE(x.cantidad_fisica,0);

-- 10. Cobertura temporal: noviembre de 2025 completo
SELECT COUNT(DISTINCT fecha_vuelo) AS dias_con_vuelos,
       DATE_FORMAT(MIN(fecha_vuelo), '%Y-%m-%d') AS primera_fecha,
       DATE_FORMAT(MAX(fecha_vuelo), '%Y-%m-%d') AS ultima_fecha,
       COUNT(*) AS total_vuelos
FROM vuelo_especifico;

-- 11. Columnas clave que usa el PBIX actual: cada tabla debe mostrar 0 faltantes
SELECT tabla, SUM(falta) columnas_faltantes
FROM (
  SELECT 'aeropuerto' tabla, CASE WHEN COUNT(*)=5 THEN 0 ELSE 1 END falta
  FROM information_schema.columns
  WHERE table_schema='aerolinea_db_v2' AND table_name='aeropuerto'
    AND column_name IN ('id_aeropuerto','codigo_iata','nombre_aeropuerto','ciudad','pais')
  UNION ALL
  SELECT 'avion', CASE WHEN COUNT(*)=4 THEN 0 ELSE 1 END
  FROM information_schema.columns
  WHERE table_schema='aerolinea_db_v2' AND table_name='avion'
    AND column_name IN ('id_avion','matricula','modelo','capacidad_total')
  UNION ALL
  SELECT 'avion_clase_asientos', CASE WHEN COUNT(*)=4 THEN 0 ELSE 1 END
  FROM information_schema.columns
  WHERE table_schema='aerolinea_db_v2' AND table_name='avion_clase_asientos'
    AND column_name IN ('id_distribucion','id_avion','id_cabina','cantidad_asientos')
  UNION ALL
  SELECT 'vuelo_programado', CASE WHEN COUNT(*)=6 THEN 0 ELSE 1 END
  FROM information_schema.columns
  WHERE table_schema='aerolinea_db_v2' AND table_name='vuelo_programado'
    AND column_name IN ('id_vuelo_programado','numero_vuelo','id_aeropuerto_origen','id_aeropuerto_destino','hora_salida','hora_llegada')
  UNION ALL
  SELECT 'vuelo_especifico', CASE WHEN COUNT(*)=5 THEN 0 ELSE 1 END
  FROM information_schema.columns
  WHERE table_schema='aerolinea_db_v2' AND table_name='vuelo_especifico'
    AND column_name IN ('id_vuelo_especifico','id_vuelo_programado','id_avion_asignado','fecha_vuelo','estado')
  UNION ALL
  SELECT 'demanda_vuelo', CASE WHEN COUNT(*)=5 THEN 0 ELSE 1 END
  FROM information_schema.columns
  WHERE table_schema='aerolinea_db_v2' AND table_name='demanda_vuelo'
    AND column_name IN ('id_demanda','id_vuelo_especifico','fecha_hora','reservas_realizadas','porcentaje_ocupacion')
  UNION ALL
  SELECT 'segmento_vuelo', CASE WHEN COUNT(*)=11 THEN 0 ELSE 1 END
  FROM information_schema.columns
  WHERE table_schema='aerolinea_db_v2' AND table_name='segmento_vuelo'
    AND column_name IN ('id_segmento','id_pnr','id_pasajero','id_vuelo_especifico','id_tarifa','id_asiento','precio_final_pagado','fecha_reserva','fecha_checkin','fecha_abordaje','estado_segmento')
  UNION ALL
  SELECT 'pago', CASE WHEN COUNT(*)=6 THEN 0 ELSE 1 END
  FROM information_schema.columns
  WHERE table_schema='aerolinea_db_v2' AND table_name='pago'
    AND column_name IN ('id_pago','id_pnr','metodo_pago','monto_total','fecha','estado')
) q
GROUP BY tabla
ORDER BY tabla;
