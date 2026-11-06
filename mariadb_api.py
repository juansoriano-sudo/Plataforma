import pymysql
import pymysql.cursors
from dbutils.pooled_db import PooledDB
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

DB_CONFIG = {
    "host":     "192.168.118.58",
    "port":     3306,
    "user":     "juasorc",
    "password": "F7nant723$",
    "database": "LogMotorFirma",
    "charset":  "utf8mb4",
    "connect_timeout": 10,
    "cursorclass": pymysql.cursors.DictCursor
}

# ✅ Pool creado una sola vez al arrancar Flask
pool = PooledDB(
    creator=pymysql,
    maxconnections=15,   # máximo simultáneo — ajustar según max_connections de MariaDB
    mincached=2,         # conexiones listas desde el inicio
    maxcached=5,         # máximo idle en espera
    blocking=True,       # espera si el pool está lleno, no lanza error inmediato
    **DB_CONFIG
)

SELECT_COLS = (
    "SELECT Codigo, Clave, Fecha, Documento, CanalCodigo, "
    "FuncionalidadCodigo, TipoCodigo, ProcesoCodigo, "
    "Clase, Metodo, Descripcion, Adicional, "
    "Transaccion, Rq, Rs, Ip, Sesion "
)

def get_connection():
    return pool.connection()  # ✅ toma del pool, no abre nueva conexión TCP

def build_historical_table(fecha_ref):
    if not fecha_ref:
        return "Log_" + datetime.now().strftime("%Y%m")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return "Log_" + datetime.strptime(fecha_ref[:19], fmt).strftime("%Y%m")
        except ValueError:
            continue
    return "Log_" + datetime.now().strftime("%Y%m")

def query_table(cur, table, id_solicitud, descripcion):
    sql = (
        SELECT_COLS +
        f"FROM {table} "
        "WHERE Documento = %s "
        "AND Descripcion LIKE %s "
        "ORDER BY Fecha DESC "
        "LIMIT 1"
    )
    cur.execute(sql, (id_solicitud, f"%{descripcion}%"))
    return cur.fetchone()

@app.route("/query", methods=["GET"])
def query_log():
    id_solicitud = request.args.get("idSolicitud", "").strip()
    descripcion  = request.args.get("descripcion", "Inicia proceso de Firma").strip()
    fecha_ref    = request.args.get("fechaRef", "").strip()

    if not id_solicitud:
        return jsonify({"error": "idSolicitud es requerido", "Rq": ""}), 400

    result = {"Rq": "", "Descripcion": "", "Fecha": "", "error": "", "tabla_usada": ""}
    row = None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            row = query_table(cur, "Log", id_solicitud, descripcion)
            if row:
                result["tabla_usada"] = "Log"
            else:
                tabla_hist = build_historical_table(fecha_ref)
                row = query_table(cur, tabla_hist, id_solicitud, descripcion)
                if row:
                    result["tabla_usada"] = tabla_hist
                else:
                    result["tabla_usada"] = f"Log + {tabla_hist}"
                    result["error"] = f"Sin resultados para Documento={id_solicitud}"

        if row:
            for k, v in row.items():
                result[k] = str(v) if v is not None else ""

    except Exception as e:
        result["error"] = f"Error BD: {str(e)}"
    finally:
        conn.close()  # ✅ devuelve al pool, no cierra TCP real

    return jsonify(result)
# ==========================================
# 🚀 ENDPOINT DE SLAs + INSIGHTS ANALÍTICOS
# ==========================================
@app.route("/reporte-sla", methods=["GET"])
def reporte_sla():
    
    sql_etapas = """
    SELECT 
    DiaProceso,
    Etapa_Negocio,
    CASE 
        WHEN MAX(ErrorCode_Por_Doc) = 2 THEN 'Timeout de Red (Api/Tercero)'
        WHEN MAX(ErrorCode_Por_Doc) = 3 THEN 'Timeout Base de Datos (600 seg)'
        WHEN MAX(ErrorCode_Por_Doc) = 1 THEN 'Excepción Técnica Detectada'
        ELSE 'Sin Errores Técnicos' 
    END AS Diagnostico_Principal_Error,
    -- 🟢 Ahora el volumen refleja estrictamente los casos únicos impactados
    COUNT(IdProceso) AS Total_Clientes_Afectados,
    SUM(Errores_Por_Doc) AS Clientes_Con_Error_Tecnico,
    ROUND(AVG(Minutos_Transcurridos), 2) AS Tiempo_Promedio_Espera_Minutos,
    ROUND(MAX(Minutos_Transcurridos), 2) AS Tiempo_Maximo_Espera_Minutos,
    -- 🟢 Severidades ajustadas para un ecosistema exclusivo de errores
    CASE 
        WHEN COUNT(IdProceso) >= 5 THEN '🔴 CRÍTICO (Fallo Masivo)'
        ELSE '🟡 ADVERTENCIA (Errores Aislados)' 
    END AS Nivel_Severidad
FROM (
    SELECT 
        DATE(l.Fecha) AS DiaProceso, 
        l.Documento AS IdProceso, 
        CASE 
            WHEN l.Metodo = 'SavePendingSignature' THEN '0. Otros / Transición'
            WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%GetDataClient%' OR l.Descripcion LIKE '%APIAgilSOA%' THEN '1. Cliente consulta documentos'
            WHEN l.Descripcion LIKE '%Inicia proceso de Firma.%' OR l.Descripcion LIKE 'Inicia proceso de Firma' OR l.Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR l.Descripcion LIKE '%BiometricState%' OR l.Descripcion LIKE '%Biometria%' THEN '2. Biometría y firma Inicial de cliente'
            WHEN (l.Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') OR l.Descripcion LIKE '%WsSing%') THEN '3. Firma Digital (WsSing)'
            WHEN (l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' OR l.Descripcion LIKE '%Deceval%' OR l.Descripcion LIKE '%pagare%') THEN '4. Firma Digital (Deceval)'
            WHEN (l.Metodo IN ('SavePdfAsync', 'GetSignedFiles', 'SendStateToAgil', 'HandleReportingProcess', 'SendFinalState', 'HandleResponse', 'ReportOriginator', 'SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') OR l.Descripcion LIKE '%envio de correo%' OR l.Descripcion LIKE '%proceso de notificacion%' OR l.Descripcion LIKE '%Inicia proceso de guardar PDF%' OR l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%') THEN '5. Almacenamiento PDF y reporte a ágil'
            ELSE '0. Otros / Transición' 
        END AS Etapa_Negocio,
        MAX(CASE
            WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%already exists%' THEN 0
            WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error durante el proceso de validacion de response Agil%' THEN 0
            WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%There is an error in XML document%' THEN 0
            WHEN ((l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' OR l.Descripcion LIKE '%Deceval%' OR l.Descripcion LIKE '%pagare%') AND COALESCE(m.Deceval_Exitoso, 0) = 1) THEN 0
            WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout of 600 seconds%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%TimeoutException%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%HttpClient.Timeout%' THEN 2
            WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%' THEN 1
            ELSE 0
        END) AS ErrorCode_Por_Doc,
        MAX(CASE
            WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%already exists%' THEN 0
            WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error durante el proceso de validacion de response Agil%' THEN 0
            WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%There is an error in XML document%' THEN 0
            WHEN ((l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' OR l.Descripcion LIKE '%Deceval%' OR l.Descripcion LIKE '%pagare%') AND COALESCE(m.Deceval_Exitoso, 0) = 1) THEN 0
            WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout of 600 seconds%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%TimeoutException%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%HttpClient.Timeout%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%' THEN 1
            ELSE 0
        END) AS Errores_Por_Doc,
        ROUND(GREATEST(TIMESTAMPDIFF(SECOND, MIN(l.Fecha), CASE WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%GetDataClient%' OR l.Descripcion LIKE '%APIAgilSOA%' THEN COALESCE(m.Hora_Corte, MAX(l.Fecha)) ELSE MAX(l.Fecha) END), 0) / 60.0, 2) AS Minutos_Transcurridos
    FROM LogMotorFirma.Log l
    LEFT JOIN (
        SELECT 
            Documento,
            MIN(CASE WHEN Descripcion LIKE '%Inicia proceso de Firma.%' OR Descripcion LIKE 'Inicia proceso de Firma' OR Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR Descripcion LIKE '%BiometricState%' OR Descripcion LIKE '%Biometria%' THEN Fecha END) AS Hora_Corte,
            MAX(CASE WHEN Descripcion LIKE '%Proceso de firma Deceval exitoso%' THEN 1 ELSE 0 END) AS Deceval_Exitoso
        FROM LogMotorFirma.Log
        WHERE Fecha >= CURDATE()
          AND Documento IS NOT NULL AND Documento <> ''
        GROUP BY Documento
    ) AS m ON l.Documento = m.Documento
    WHERE l.Fecha >= CURDATE()
      AND l.Documento IS NOT NULL AND l.Documento <> ''
      AND l.Documento REGEXP '^[0-9]+$'
      AND CAST(l.Documento AS UNSIGNED) > 50000
      AND l.Metodo NOT LIKE 'GetPendingSignatures%'
    GROUP BY DATE(l.Fecha), l.Documento,
        CASE 
            WHEN l.Metodo = 'SavePendingSignature' THEN '0. Otros / Transición'
            WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%GetDataClient%' OR l.Descripcion LIKE '%APIAgilSOA%' THEN '1. Cliente consulta documentos'
            WHEN l.Descripcion LIKE '%Inicia proceso de Firma.%' OR l.Descripcion LIKE 'Inicia proceso de Firma' OR l.Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR l.Descripcion LIKE '%BiometricState%' OR l.Descripcion LIKE '%Biometria%' THEN '2. Biometría y firma Inicial de cliente'
            WHEN (l.Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') OR l.Descripcion LIKE '%WsSing%') THEN '3. Firma Digital (WsSing)'
            WHEN (l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' OR l.Descripcion LIKE '%Deceval%' OR l.Descripcion LIKE '%pagare%') THEN '4. Firma Digital (Deceval)'
            WHEN (l.Metodo IN ('SavePdfAsync', 'GetSignedFiles', 'SendStateToAgil', 'HandleReportingProcess', 'SendFinalState', 'HandleResponse', 'ReportOriginator', 'SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') OR l.Descripcion LIKE '%envio de correo%' OR l.Descripcion LIKE '%proceso de notificacion%' OR l.Descripcion LIKE '%Inicia proceso de guardar PDF%' OR l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%') THEN '5. Almacenamiento PDF y reporte a ágil'
            ELSE '0. Otros / Transición' 
        END
) AS Layer3
-- 🎯 FILTROS EXCLUSIVOS DE CAÍDAS OPERATIVAS
WHERE Etapa_Negocio != '0. Otros / Transición'
  AND Errores_Por_Doc > 0 -- 🛑 Elimina de raíz cualquier rastro de trámites limpios/exitosos
GROUP BY DiaProceso, Etapa_Negocio
ORDER BY Etapa_Negocio ASC;
    """
    
    sql_errores_etapa = """
    SELECT 
        IdSolicitud,
        Etapa_Fallo,
        MAX(Hora_Fallo) AS Hora_Fallo,
        MAX(Tipo_Error) AS Tipo_Error,
        MAX(Mensaje_Log_Tecnico) AS Mensaje_Log_Tecnico
    FROM (
        SELECT 
            l.Documento AS IdSolicitud,
            CASE 
                WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%GetDataClient%' OR l.Descripcion LIKE '%APIAgilSOA%' THEN '1. Consulta documentos'
                WHEN l.Descripcion LIKE '%Inicia proceso de Firma.%' OR l.Descripcion LIKE 'Inicia proceso de Firma' OR l.Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR l.Descripcion LIKE '%BiometricState%' OR l.Descripcion LIKE '%Biometria%' THEN '2. Biometría / Firma'
                WHEN (l.Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') OR l.Descripcion LIKE '%WsSing%') THEN '3. WsSing'
                WHEN (l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' OR l.Descripcion LIKE '%Deceval%' OR l.Descripcion LIKE '%pagare%') THEN '4. Deceval'
                WHEN (l.Metodo IN ('SavePdfAsync', 'GetSignedFiles', 'SendStateToAgil', 'HandleReportingProcess', 'SendFinalState', 'HandleResponse', 'ReportOriginator', 'SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') OR l.Descripcion LIKE '%envio de correo%' OR l.Descripcion LIKE '%proceso de notificacion%' OR l.Descripcion LIKE '%Inicia proceso de guardar PDF%' OR l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%') THEN '5. Almacenamiento/Ágil'
                ELSE 'Otro Proceso' 
            END AS Etapa_Fallo,
            l.Fecha AS Hora_Fallo,
            CASE 
                WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout of 600 seconds%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%TimeoutException%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%HttpClient.Timeout%' THEN 'TIMEOUT / CONEXIÓN CORTADA'
                ELSE 'EXCEPCIÓN TÉCNICA' 
            END AS Tipo_Error,
            LEFT(CONCAT_WS(' | ', l.Descripcion, l.Adicional, l.Rs), 250) AS Mensaje_Log_Tecnico
        FROM LogMotorFirma.Log l
        LEFT JOIN (
            SELECT 
                Documento,
                MAX(CASE WHEN Descripcion LIKE '%Proceso de firma Deceval exitoso%' THEN 1 ELSE 0 END) AS Deceval_Exitoso
            FROM LogMotorFirma.Log
            WHERE Fecha >= CURDATE()
            GROUP BY Documento
        ) AS m ON l.Documento = m.Documento
        WHERE l.Fecha >= CURDATE()
          AND l.Documento IS NOT NULL AND l.Documento <> ''
          AND l.Documento REGEXP '^[0-9]+$'
          AND CAST(l.Documento AS UNSIGNED) > 50000
          AND (CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout of 600 seconds%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%TimeoutException%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%HttpClient.Timeout%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%')
          AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%already exists%'
          AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error durante el proceso de validacion de response Agil%'
          AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%There is an error in XML document%'
          AND CASE WHEN (l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' OR l.Descripcion LIKE '%Deceval%' OR l.Descripcion LIKE '%pagare%') AND COALESCE(m.Deceval_Exitoso, 0) = 1 THEN 1 ELSE 0 END = 0
    ) AS BaseErrores
    GROUP BY IdSolicitud, Etapa_Fallo
    ORDER BY Hora_Fallo DESC;
    """
    sql_tiempo_etapas = """
    SELECT 
    Etapa_Negocio AS Macro_Flujo_Negocio,
    COUNT(IdProceso) AS Total_Ejecuciones,
    -- Forzamos a 0 las columnas operacionales que ya no aplican por el filtro de riesgo
    0 AS `0_a_1_Minuto`,
    0 AS `1_a_2_Minutos`,
    0 AS `2_a_3_Minutos`,
    SUM(CASE WHEN Minutos_Transcurridos > 3.00 AND Minutos_Transcurridos <= 5.00 THEN 1 ELSE 0 END) AS `3_a_5_Minutos`,
    SUM(CASE WHEN Minutos_Transcurridos > 5.00 THEN 1 ELSE 0 END) AS `Mas_de_5_Minutos`
FROM (
    SELECT 
        IdProceso,
        Etapa_Negocio,
        ROUND(GREATEST(TIMESTAMPDIFF(SECOND, MIN(Fecha), CASE WHEN Etapa_Negocio = '1. Cliente consulta documentos' THEN COALESCE(MAX(Corte_E1), MAX(Fecha)) WHEN Etapa_Negocio = '2. Biometría y firma Inicial de cliente.' THEN COALESCE(MAX(Corte_E2), MAX(Fecha)) WHEN Etapa_Negocio = '3. Firma Digital (WsSing)' THEN COALESCE(MAX(Corte_E3), MAX(Fecha)) WHEN Etapa_Negocio = '4. Firma Digital (Deceval)' THEN COALESCE(MAX(Corte_E4), MAX(Fecha)) ELSE MAX(Fecha) END), 0) / 60.0, 2) AS Minutos_Transcurridos
    FROM (
        SELECT 
            l.Documento AS IdProceso, 
            l.Fecha,
            m.Corte_E1, m.Corte_E2, m.Corte_E3, m.Corte_E4,
            CASE 
                WHEN l.Metodo = 'SavePendingSignature' THEN '0. Otros / Transición'
                WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%GetDataClient%' OR l.Descripcion LIKE '%APIAgilSOA%' THEN '1. Cliente consulta documentos'
                WHEN l.Descripcion LIKE '%Inicia proceso de Firma.%' OR l.Descripcion LIKE 'Inicia proceso de Firma' OR l.Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR l.Descripcion LIKE '%BiometricState%' OR l.Descripcion LIKE '%Biometria%' THEN '2. Biometría y firma Inicial de cliente.'
                WHEN (l.Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') OR l.Descripcion LIKE '%WsSing%') AND COALESCE(m.Hit_Etapa3, 0) = 1 THEN '3. Firma Digital (WsSing)'
                WHEN (l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' OR l.Descripcion LIKE '%Deceval%' OR l.Descripcion LIKE '%pagare%') AND COALESCE(m.Hit_Etapa4, 0) = 1 THEN '4. Firma Digital (Deceval)'
                WHEN (l.Metodo IN ('SavePdfAsync', 'GetSignedFiles', 'SendStateToAgil', 'HandleReportingProcess', 'SendFinalState', 'HandleResponse', 'ReportOriginator', 'SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') OR l.Descripcion LIKE '%envio de correo%' OR l.Descripcion LIKE '%proceso de notificacion%' OR l.Descripcion LIKE '%Inicia proceso de guardar PDF%' OR l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%') AND COALESCE(m.Hit_Etapa5, 0) = 1 THEN '5. Almacenamiento PDF y reporte a ágil'
                ELSE '0. Otros / Transición' 
            END AS Etapa_Negocio
        FROM LogMotorFirma.Log l
        LEFT JOIN (
            SELECT 
                Documento,
                MIN(CASE WHEN Descripcion LIKE '%Inicia proceso de Firma.%' OR Descripcion LIKE 'Inicia proceso de Firma' OR Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR Descripcion LIKE '%BiometricState%' OR Descripcion LIKE '%Biometria%' THEN Fecha END) AS Corte_E1,
                MIN(CASE WHEN Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync') OR Descripcion LIKE '%Inicia proceso de WsSing%' OR Descripcion LIKE '%Inicia proceso de Firma WsSing%' THEN Fecha END) AS Corte_E2,
                MIN(CASE WHEN Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'DecevalSingProcess') OR Descripcion LIKE '%Inicia proceso de Firma Deceval%' THEN Fecha END) AS Corte_E3,
                MIN(CASE WHEN Descripcion LIKE '%Inicia proceso de guardar PDF%' OR Descripcion LIKE 'Inicia proceso de guardar PDF' THEN Fecha END) AS Corte_E4,
                MAX(CASE WHEN Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync') OR Descripcion LIKE '%Inicia proceso de WsSing%' OR Descripcion LIKE '%Inicia proceso de Firma WsSing%' THEN 1 ELSE 0 END) AS Hit_Etapa3,
                MAX(CASE WHEN Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'DecevalSingProcess') OR Descripcion LIKE '%Inicia proceso de Firma Deceval%' THEN 1 ELSE 0 END) AS Hit_Etapa4,
                MAX(CASE WHEN Descripcion LIKE '%Nuevo estado de la solicitud: 1000%' THEN 1 ELSE 0 END) AS Hit_Etapa5
            FROM LogMotorFirma.Log
            WHERE Fecha >= CURDATE() AND Documento IS NOT NULL AND Documento <> ''
            GROUP BY Documento
        ) AS m ON l.Documento = m.Documento
        WHERE l.Fecha >= CURDATE() 
          AND l.Documento IS NOT NULL AND l.Documento <> '' 
          AND l.Documento REGEXP '^[0-9]+$' 
          AND CAST(l.Documento AS UNSIGNED) > 50000 
          AND l.Metodo NOT LIKE 'GetPendingSignatures%'
          AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%There is an error in XML document%'
          AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error durante el proceso de validacion de response Agil%'
    ) AS BaseAsignada
    WHERE Etapa_Negocio != '0. Otros / Transición'
    GROUP BY IdProceso, Etapa_Negocio
) AS Agrupado
WHERE Minutos_Transcurridos > 3.00 -- 🛑 EL ESCUDO: Solo deja pasar trámites estancados en zona de riesgo
GROUP BY Etapa_Negocio
ORDER BY Etapa_Negocio ASC;
    """
    sql_lentos_detalle = """
    SELECT 
        IdProceso AS `ID Solicitud`,
        Hora_Fallo AS `Hora del Fallo`,
        Etapa_Negocio AS `Etapa Afectada`,
        CASE 
            WHEN Tipo_Error != 'SIN ERROR' THEN Tipo_Error 
            ELSE CONCAT('(> ', Minutos_Transcurridos, ' min)') 
        END AS `Clasificación`,
        COALESCE(CONVERT(Mensaje_Log USING utf8mb4), 'Sin traza de error técnico (Inactividad o encolamiento)') AS `Log Técnico (Extracto)`
    FROM (
        SELECT 
            IdProceso,
            Etapa_Negocio,
            MAX(Fecha) AS Hora_Fallo,
            ROUND(GREATEST(TIMESTAMPDIFF(SECOND, MIN(Fecha), CASE WHEN Etapa_Negocio = '1. Cliente consulta documentos' THEN COALESCE(MAX(Corte_E1), MAX(Fecha)) WHEN Etapa_Negocio = '2. Biometría y firma Inicial de cliente.' THEN COALESCE(MAX(Corte_E2), MAX(Fecha)) WHEN Etapa_Negocio = '3. Firma Digital (WsSing)' THEN COALESCE(MAX(Corte_E3), MAX(Fecha)) WHEN Etapa_Negocio = '4. Firma Digital (Deceval)' THEN COALESCE(MAX(Corte_E4), MAX(Fecha)) ELSE MAX(Fecha) END), 0) / 60.0, 2) AS Minutos_Transcurridos,
            MAX(CASE 
                WHEN CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '%Timeout of 600 seconds%' OR CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '%TimeoutException%' OR CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '%HttpClient.Timeout%' THEN 'TIMEOUT / CONEXIÓN CORTADA'
                WHEN (
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '% Error %' OR 
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE 'Error %' OR 
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '% Fallo %' OR 
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE 'Fallo %' OR 
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '%Exception%'
                ) 
                -- 🟢 IGNORAMOS LOS ERRORES DE XML / ÁGIL PARA QUE NO SE MARQUEN COMO EXCEPCIÓN
                AND CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) NOT LIKE '%There is an error in XML document%'
                AND CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) NOT LIKE '%Error durante el proceso de validacion de response Agil%'
                THEN 'EXCEPCIÓN TÉCNICA'
                ELSE 'SIN ERROR' 
            END) AS Tipo_Error,
            MAX(CASE 
                WHEN CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '%Timeout of 600 seconds%' OR CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '%TimeoutException%' OR CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '%HttpClient.Timeout%' THEN CONVERT(LEFT(CONCAT_WS(' | ', Descripcion, Adicional, Rs), 250) USING utf8mb4)
                WHEN (
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '% Error %' OR 
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE 'Error %' OR 
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '% Fallo %' OR 
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE 'Fallo %' OR 
                    CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) LIKE '%Exception%'
                ) 
                -- 🟢 IGNORAMOS LOS ERRORES DE XML / ÁGIL PARA QUE NO SE EXTRAIGAN EN EL TEXTO DEL LOG
                AND CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) NOT LIKE '%There is an error in XML document%'
                AND CONVERT(CONCAT_WS(' ', Descripcion, Adicional, Rs) USING utf8mb4) NOT LIKE '%Error durante el proceso de validacion de response Agil%'
                THEN CONVERT(LEFT(CONCAT_WS(' | ', Descripcion, Adicional, Rs), 250) USING utf8mb4)
            END) AS Mensaje_Log
        FROM (
            SELECT 
                l.Documento AS IdProceso, 
                l.Fecha,
                l.Descripcion, l.Adicional, l.Rs,
                m.Corte_E1, m.Corte_E2, m.Corte_E3, m.Corte_E4,
                CASE 
                    WHEN l.Metodo = 'SavePendingSignature' THEN '0. Otros / Transición'
                    WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%GetDataClient%' OR l.Descripcion LIKE '%APIAgilSOA%' THEN '1. Cliente consulta documentos'
                    WHEN l.Descripcion LIKE '%Inicia proceso de Firma.%' OR l.Descripcion LIKE 'Inicia proceso de Firma' OR l.Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR l.Descripcion LIKE '%BiometricState%' OR l.Descripcion LIKE '%Biometria%' THEN '2. Biometría y firma Inicial de cliente.'
                    WHEN (l.Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') OR l.Descripcion LIKE '%WsSing%') AND COALESCE(m.Hit_Etapa3, 0) = 1 THEN '3. Firma Digital (WsSing)'
                    WHEN (l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' OR l.Descripcion LIKE '%Deceval%' OR l.Descripcion LIKE '%pagare%') AND COALESCE(m.Hit_Etapa4, 0) = 1 THEN '4. Firma Digital (Deceval)'
                    WHEN (l.Metodo IN ('SavePdfAsync', 'GetSignedFiles', 'SendStateToAgil', 'HandleReportingProcess', 'SendFinalState', 'HandleResponse', 'ReportOriginator', 'SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') OR l.Descripcion LIKE '%envio de correo%' OR l.Descripcion LIKE '%proceso de notificacion%' OR l.Descripcion LIKE '%Inicia proceso de guardar PDF%' OR l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%') AND COALESCE(m.Hit_Etapa5, 0) = 1 THEN '5. Almacenamiento PDF y reporte a ágil'
                    ELSE '0. Otros / Transición' 
                END AS Etapa_Negocio
            FROM LogMotorFirma.Log l
            LEFT JOIN (
                SELECT 
                    Documento,
                    MIN(CASE WHEN Descripcion LIKE '%Inicia proceso de Firma.%' OR Descripcion LIKE 'Inicia proceso de Firma' OR Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR Descripcion LIKE '%BiometricState%' OR Descripcion LIKE '%Biometria%' THEN Fecha END) AS Corte_E1,
                    MIN(CASE WHEN Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync') OR Descripcion LIKE '%Inicia proceso de WsSing%' OR Descripcion LIKE '%Inicia proceso de Firma WsSing%' THEN Fecha END) AS Corte_E2,
                    MIN(CASE WHEN Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'DecevalSingProcess') OR Descripcion LIKE '%Inicia proceso de Firma Deceval%' THEN Fecha END) AS Corte_E3,
                    MIN(CASE WHEN Descripcion LIKE '%Inicia proceso de guardar PDF%' OR Descripcion LIKE 'Inicia proceso de guardar PDF' THEN Fecha END) AS Corte_E4,
                    MAX(CASE WHEN Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync') OR Descripcion LIKE '%Inicia proceso de WsSing%' OR Descripcion LIKE '%Inicia proceso de Firma WsSing%' THEN 1 ELSE 0 END) AS Hit_Etapa3,
                    MAX(CASE WHEN Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'DecevalSingProcess') OR Descripcion LIKE '%Inicia proceso de Firma Deceval%' THEN 1 ELSE 0 END) AS Hit_Etapa4,
                    MAX(CASE WHEN Descripcion LIKE '%Nuevo estado de la solicitud: 1000%' THEN 1 ELSE 0 END) AS Hit_Etapa5
                FROM LogMotorFirma.Log
                WHERE Fecha >= CURDATE() AND Documento IS NOT NULL AND Documento <> ''
                GROUP BY Documento
            ) AS m ON l.Documento = m.Documento
            WHERE l.Fecha >= CURDATE() AND l.Documento IS NOT NULL AND l.Documento <> '' AND l.Documento REGEXP '^[0-9]+$' AND CAST(l.Documento AS UNSIGNED) > 50000 AND l.Metodo NOT LIKE 'GetPendingSignatures%'
        ) AS BaseAsignada
        WHERE Etapa_Negocio != '0. Otros / Transición'
        GROUP BY IdProceso, Etapa_Negocio
    ) AS Agrupado
    WHERE Minutos_Transcurridos > 3.00
    -- 🟢 ORDENAMOS PRIMERO POR ETAPA (Para agruparlos) Y LUEGO POR MINUTOS
    ORDER BY Etapa_Negocio ASC, Minutos_Transcurridos DESC;
    """
    sql_Cliente_consulta_documentos = """
    SELECT 
        Documento_Cliente,
        '1. Preparación y Radicación' AS Etapa_Negocio,
        Hora_Inicio_Etapa,
        COALESCE(Hora_Corte_Etapa, Ultimo_Registro_Etapa1) AS Hora_Fin_Calculada,
        ROUND(GREATEST(TIMESTAMPDIFF(SECOND, Hora_Inicio_Etapa, COALESCE(Hora_Corte_Etapa, Ultimo_Registro_Etapa1)), 0) / 60.0, 2) AS Minutos_Procesamiento_Real,
        Detalle_Error_Tecnico
    FROM (
        SELECT 
            l.Documento AS Documento_Cliente,
            MIN(CASE WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%GetDataClient%' OR l.Descripcion LIKE '%APIAgilSOA%' THEN l.Fecha END) AS Hora_Inicio_Etapa,
            MAX(CASE WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%GetDataClient%' OR l.Descripcion LIKE '%APIAgilSOA%' THEN l.Fecha END) AS Ultimo_Registro_Etapa1,
            MIN(CASE WHEN l.Descripcion LIKE '%Inicia proceso de Firma.%' OR l.Descripcion LIKE 'Inicia proceso de Firma' THEN l.Fecha END) AS Hora_Corte_Etapa,
            
            -- 🟢 NUEVO: Extraemos el texto del error en lugar de contarlo
            MAX(CASE 
                WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%GetDataClient%' OR l.Descripcion LIKE '%APIAgilSOA%' THEN 
                    CASE 
                        WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout of 600 seconds%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%TimeoutException%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%HttpClient.Timeout%' THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                        WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%' THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                        ELSE NULL 
                    END 
                ELSE NULL 
            END) AS Detalle_Error_Tecnico

        FROM LogMotorFirma.Log l
        WHERE l.Fecha >= CURDATE()
        AND l.Documento IS NOT NULL 
        AND l.Documento <> '' 
        AND l.Documento REGEXP '^[0-9]+$' 
        AND CAST(l.Documento AS UNSIGNED) > 50000 
        AND l.Metodo NOT LIKE 'GetPendingSignatures%'
        GROUP BY l.Documento
    ) AS BaseLimpia
    WHERE Hora_Inicio_Etapa IS NOT NULL
      AND Detalle_Error_Tecnico IS NOT NULL
    ORDER BY Minutos_Procesamiento_Real DESC
    LIMIT 10;
    """

    sql_Biometria = """
    SELECT 
        Documento_Cliente,
        '2. Biometría y Firma Cliente' AS Etapa_Negocio,
        Hora_Inicio_Etapa,
        COALESCE(Hora_Corte_Etapa, Ultimo_Registro_Etapa2) AS Hora_Fin_Calculada,
        ROUND(TIMESTAMPDIFF(SECOND, Hora_Inicio_Etapa, COALESCE(Hora_Corte_Etapa, Ultimo_Registro_Etapa2)) / 60.0, 2) AS Minutos_Atascado,
        Detalle_Error_Tecnico
    FROM (
        SELECT 
            l.Documento AS Documento_Cliente,
            MIN(CASE 
                WHEN l.Descripcion LIKE '%Inicia proceso de Firma.%' OR l.Descripcion LIKE 'Inicia proceso de Firma' OR l.Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR l.Descripcion LIKE '%BiometricState%' OR l.Descripcion LIKE '%Biometria%' 
                THEN l.Fecha 
            END) AS Hora_Inicio_Etapa,
            MAX(CASE 
                WHEN l.Descripcion LIKE '%Inicia proceso de Firma.%' OR l.Descripcion LIKE 'Inicia proceso de Firma' OR l.Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR l.Descripcion LIKE '%BiometricState%' OR l.Descripcion LIKE '%Biometria%' 
                THEN l.Fecha 
            END) AS Ultimo_Registro_Etapa2,
            MIN(CASE 
                WHEN l.Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') OR l.Descripcion LIKE '%WsSing%' 
                THEN l.Fecha 
            END) AS Hora_Corte_Etapa,
            
            -- 🟢 NUEVO: Extracción de error
            MAX(CASE 
                WHEN l.Descripcion LIKE '%Inicia proceso de Firma.%' OR l.Descripcion LIKE 'Inicia proceso de Firma' OR l.Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR l.Descripcion LIKE '%BiometricState%' OR l.Descripcion LIKE '%Biometria%' THEN
                    CASE
                        WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout of 600 seconds%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%TimeoutException%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%HttpClient.Timeout%' THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                        WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%' THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                        ELSE NULL
                    END
                ELSE NULL
            END) AS Detalle_Error_Tecnico

        FROM LogMotorFirma.Log l
        WHERE l.Fecha >= CURDATE()
          AND l.Documento IS NOT NULL 
          AND l.Documento <> '' 
          AND l.Documento REGEXP '^[0-9]+$' 
          AND CAST(l.Documento AS UNSIGNED) > 50000 
          AND l.Metodo NOT LIKE 'GetPendingSignatures%'
        GROUP BY l.Documento
    ) AS BaseLimpia
    WHERE Hora_Inicio_Etapa IS NOT NULL
      AND Detalle_Error_Tecnico IS NOT NULL
    ORDER BY Minutos_Atascado DESC
    LIMIT 10;
    """

    sql_WsSing = """
    SELECT 
        Documento_Cliente,
        '3. Firma Digital WsSing' AS Etapa_Negocio,
        Hora_Inicio_Etapa,
        COALESCE(Hora_Corte_Etapa, Ultimo_Registro_WsSing) AS Hora_Fin_Calculada,
        ROUND(TIMESTAMPDIFF(SECOND, Hora_Inicio_Etapa, COALESCE(Hora_Corte_Etapa, Ultimo_Registro_WsSing)) / 60.0, 2) AS Minutos_Atascado,
        Detalle_Error_Tecnico
    FROM (
        SELECT 
            l.Documento AS Documento_Cliente,
            MIN(CASE 
                WHEN l.Descripcion LIKE '%Inicia proceso de WsSing%' 
                  OR l.Descripcion LIKE '%Inicia proceso de Firma WsSing%'
                THEN l.Fecha 
            END) AS Hora_Inicio_Etapa,
            MIN(CASE 
                WHEN l.Descripcion LIKE '%Proceso de firma WsSing exitoso%' 
                  OR l.Descripcion LIKE '%Proceso de firmado en WsSing Exitoso%'
                THEN l.Fecha 
            END) AS Hora_Corte_Etapa,
            MAX(CASE 
                WHEN l.Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') 
                  OR l.Descripcion LIKE '%WsSing%'
                THEN l.Fecha 
            END) AS Ultimo_Registro_WsSing,
            
            -- 🟢 NUEVO: Extracción de error
            MAX(CASE 
                WHEN l.Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') 
                  OR l.Descripcion LIKE '%WsSing%' THEN
                    CASE
                        WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout of 600 seconds%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%TimeoutException%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%HttpClient.Timeout%' THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                        WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%' THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                        ELSE NULL
                    END
                ELSE NULL
            END) AS Detalle_Error_Tecnico

        FROM LogMotorFirma.Log l
        WHERE l.Fecha >= CURDATE()
          AND l.Documento IS NOT NULL 
          AND l.Documento <> '' 
          AND l.Documento REGEXP '^[0-9]+$' 
          AND CAST(l.Documento AS UNSIGNED) > 50000 
          AND l.Metodo NOT LIKE 'GetPendingSignatures%'
        GROUP BY l.Documento
    ) AS BaseLimpia
    WHERE Hora_Inicio_Etapa IS NOT NULL
      AND Detalle_Error_Tecnico IS NOT NULL
    ORDER BY Minutos_Atascado DESC
    LIMIT 10;
    """
    
    sql_Deceval = """ 
    SELECT 
        Documento_Cliente,
        '4. Legalización Deceval' AS Etapa_Negocio,
        Hora_Inicio_Etapa,
        COALESCE(Hora_Corte_Etapa, Ultimo_Registro_Deceval) AS Hora_Fin_Calculada,
        ROUND(TIMESTAMPDIFF(SECOND, Hora_Inicio_Etapa, COALESCE(Hora_Corte_Etapa, Ultimo_Registro_Deceval)) / 60.0, 2) AS Minutos_Atascado,
        Detalle_Error_Tecnico
    FROM (
        SELECT 
            l.Documento AS Documento_Cliente,
            MIN(CASE 
                WHEN l.Descripcion LIKE '%Inicia proceso de Firma Deceval%' 
                THEN l.Fecha 
            END) AS Hora_Inicio_Etapa,
            MIN(CASE 
                WHEN l.Descripcion LIKE '%Proceso de firma Deceval exitoso%' 
                THEN l.Fecha 
            END) AS Hora_Corte_Etapa,
            MAX(CASE 
                WHEN l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') 
                  OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' 
                  OR l.Descripcion LIKE '%Deceval%' 
                  OR l.Descripcion LIKE '%pagare%' 
                THEN l.Fecha 
            END) AS Ultimo_Registro_Deceval,
            
            -- 🟢 NUEVO: Extracción de error (Mantiene regla de "perdón" a Deceval)
            MAX(CASE 
                WHEN l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') 
                  OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' 
                  OR l.Descripcion LIKE '%Deceval%' 
                  OR l.Descripcion LIKE '%pagare%' THEN
                    CASE
                        WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout of 600 seconds%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%TimeoutException%' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%HttpClient.Timeout%' THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                        WHEN (CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Error %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Fallo %' OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%') 
                             AND NOT (
                                 CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error durante la verificacion de Pagare%'
                                 AND EXISTS (
                                     SELECT 1 
                                     FROM LogMotorFirma.Log l2 
                                     WHERE l2.Documento = l.Documento 
                                       AND l2.Fecha >= CURDATE() 
                                       AND l2.Descripcion LIKE '%Proceso de firma Deceval exitoso%'
                                 )
                             )
                        THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                        ELSE NULL
                    END
                ELSE NULL
            END) AS Detalle_Error_Tecnico

        FROM LogMotorFirma.Log l
        WHERE l.Fecha >= CURDATE()
          AND l.Documento IS NOT NULL 
          AND l.Documento <> '' 
          AND l.Documento REGEXP '^[0-9]+$' 
          AND CAST(l.Documento AS UNSIGNED) > 50000 
          AND l.Metodo NOT LIKE 'GetPendingSignatures%'
        GROUP BY l.Documento
    ) AS BaseLimpia
    WHERE Hora_Inicio_Etapa IS NOT NULL
      AND Detalle_Error_Tecnico IS NOT NULL
    ORDER BY Minutos_Atascado DESC
    LIMIT 10;
    """
    
    sql_Agil = """
    SELECT 
    Documento_Cliente,
    '5. Cierre y Notificación' AS Etapa_Negocio,
    Hora_Inicio_Etapa,
    COALESCE(Hora_Corte_Etapa, Ultimo_Registro_Etapa5) AS Hora_Fin_Calculada,
    ROUND(TIMESTAMPDIFF(SECOND, Hora_Inicio_Etapa, COALESCE(Hora_Corte_Etapa, Ultimo_Registro_Etapa5)) / 60.0, 2) AS Minutos_Procesamiento,
    Detalle_Error_Tecnico
FROM (
    SELECT 
        l.`Documento` AS Documento_Cliente,
        MIN(CASE 
            WHEN l.`Descripcion` LIKE '%Inicia proceso de guardar PDF%' OR l.`Descripcion` LIKE 'Inicia proceso de guardar PDF' 
            THEN l.`Fecha` 
        END) AS Hora_Inicio_Etapa,
        MAX(CASE 
            WHEN l.`Descripcion` LIKE '%Nuevo estado de la solicitud: 1000%' 
            THEN l.`Fecha` 
        END) AS Hora_Estado_1000,
        MIN(CASE 
            WHEN l.`Descripcion` LIKE '%Proceso de reporte de estado a Agil Exitoso%' OR l.`Descripcion` LIKE 'Proceso de reporte de estado a Agil Exitoso' 
            THEN l.`Fecha` 
        END) AS Hora_Corte_Etapa,
        MAX(CASE 
            WHEN l.`Metodo` IN ('SavePdfAsync', 'GetSignedFiles', 'SendStateToAgil', 'HandleReportingProcess', 'SendFinalState', 'HandleResponse', 'ReportOriginator', 'SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') 
              OR l.`Descripcion` LIKE '%envio de correo%' 
              OR l.`Descripcion` LIKE '%proceso de notificacion%' 
              OR l.`Descripcion` LIKE '%Inicia proceso de guardar PDF%'
              OR l.`Descripcion` LIKE '%Nuevo estado de la solicitud: 1000%'
            THEN l.`Fecha` 
        END) AS Ultimo_Registro_Etapa5,
        
        -- 🟢 EXTRACTOR CORREGIDO: Se inyecta la omisión explícita del error XML / Response Agil
        MAX(CASE 
            WHEN l.`Metodo` IN ('SavePdfAsync', 'GetSignedFiles', 'SendStateToAgil', 'HandleReportingProcess', 'SendFinalState', 'HandleResponse', 'ReportOriginator', 'SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') 
              OR l.`Descripcion` LIKE '%envio de correo%' 
              OR l.`Descripcion` LIKE '%proceso de notificacion%' 
              OR l.`Descripcion` LIKE '%Inicia proceso de guardar PDF%' THEN
                CASE
                    -- 1. Evaluamos si es una alerta que SÍ queremos rastrear
                    WHEN CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%Timeout of 600 seconds%' OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%TimeoutException%' OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%HttpClient.Timeout%' THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                    
                    -- 2. Evaluamos excepciones generales, aplicando los filtros de exclusión ("perdonados")
                    WHEN (CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '% Error %' OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE 'Error %' OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '% Fallo %' OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE 'Fallo %' OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%Exception%') 
                         -- 🛑 FILTROS DE EXCLUSIÓN AGREGADOS: Omitir errores XML de Ágil
                         AND CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) NOT LIKE '%There is an error in XML document%'
                         AND CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) NOT LIKE '%Error durante el proceso de validacion de response Agil%'
                         AND NOT (
                             CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error durante la verificacion de Pagare%'
                             AND EXISTS (
                                 SELECT 1 
                                 FROM LogMotorFirma.Log l2 
                                 WHERE l2.Documento = l.Documento 
                                   AND l2.Fecha >= CURDATE() 
                                   AND l2.Descripcion LIKE '%Proceso de firma Deceval exitoso%'
                             )
                         )
                    THEN LEFT(CONCAT_WS(' | ', l.Metodo, l.Descripcion, l.Adicional, l.Rs), 300)
                    ELSE NULL
                END
            ELSE NULL
        END) AS Detalle_Error_Tecnico

    FROM LogMotorFirma.Log l
    WHERE l.`Fecha` >= CURDATE()
      AND l.`Documento` IS NOT NULL 
      AND l.`Documento` <> '' 
      AND l.`Documento` REGEXP '^[0-9]+$' 
      AND CAST(l.`Documento` AS UNSIGNED) > 50000 
      AND l.`Metodo` NOT LIKE 'GetPendingSignatures%'
    GROUP BY l.`Documento`
) AS BaseLimpia
WHERE Hora_Inicio_Etapa IS NOT NULL 
  AND Hora_Estado_1000 IS NOT NULL 
  AND Hora_Estado_1000 >= Hora_Inicio_Etapa
  AND Detalle_Error_Tecnico IS NOT NULL
ORDER BY Minutos_Procesamiento DESC
LIMIT 10;
    """
    # 1. Consulta Principal de la Tabla SLA
    sql_principal = """
    SELECT 
    DiaProceso,
    Macro_Flujo_Negocio,
    CASE WHEN MAX(ErrorCode_Por_Doc) = 2 THEN 'Timeout de Red HttpClient (10 min)'
         WHEN MAX(ErrorCode_Por_Doc) = 3 THEN 'Timeout de SP (600 seg)'
         WHEN MAX(ErrorCode_Por_Doc) = 1 THEN 'Error, Fallo o Excepcion Detectada'
         ELSE 'Sin Errores' END AS Diagnostico_Principal_Error,
    COUNT(IdProceso) AS Total_Peticiones_Hits,
    SUM(Errores_Por_Doc) AS Total_Errores_Registrados,
    ROUND(AVG(DuracionMinutos), 2) AS Tiempo_Promedio_Espera_Minutos,
    ROUND(MAX(DuracionMinutos), 2) AS Tiempo_Maximo_Espera_Minutos,
    CASE WHEN MAX(DuracionMinutos) >= 15.0 THEN '🔴 CRITICO'
         WHEN MAX(DuracionMinutos) BETWEEN 5.0 AND 14.99 THEN '🟡 ADVERTENCIA'
         ELSE '🟢 Correcto' END AS Indicador_SLA,
    ROUND(((COUNT(IdProceso) - SUM(Errores_Por_Doc)) / COUNT(IdProceso)) * 100, 2) AS Porcentaje_Efectividad
FROM (
    SELECT DiaProceso, IdProceso, Macro_Flujo_Negocio, COUNT(*) AS Hits_Por_Doc,
           MAX(ErrorCode) AS ErrorCode_Por_Doc,
           MAX(EsError) AS Errores_Por_Doc,
           SUM(CASE WHEN DeltaSeconds <= 1800 THEN DeltaSeconds ELSE 0 END) / 60.0 AS DuracionMinutos
    FROM (
        SELECT DiaProceso, IdProceso, Macro_Flujo_Negocio, ErrorCode, EsError,
               IF(@prev_id = IdProceso AND @prev_flujo = Macro_Flujo_Negocio,
                  TIMESTAMPDIFF(SECOND, @prev_fecha, Fecha), 0) AS DeltaSeconds,
               @prev_id := IdProceso AS set_id,
               @prev_flujo := Macro_Flujo_Negocio AS set_flujo,
               @prev_fecha := Fecha AS set_fecha
        FROM (
            SELECT * FROM (
                SELECT DATE(l.`Fecha`) AS DiaProceso, l.`Documento` AS IdProceso, l.`Fecha`,
                    COALESCE(
                        CASE WHEN l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%Parte1%' THEN '1b. SP Client_SP_GetInfoDocBiometriaParte1'
                        WHEN l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%Parte2%' THEN '1c. SP Client_SP_GetInfoDocBiometriaParte2'
                        WHEN l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%Parte3%' THEN '1d. SP Client_SP_GetInfoDocBiometriaParte3'
                        WHEN l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%Parte4VC%' THEN '1e. SP Client_SP_GetInfoDocBiometriaParte4VC'
                        WHEN l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%GetDataClient%' THEN '1a. SP Client_SP_GetDataClientBiometria'
                        WHEN l.`Metodo` IN ('ExecuteSpBiometrics', 'GetClientBiometricData') THEN '1a. SP Client_SP_GetDataClientBiometria'
                        WHEN l.`Metodo` = 'ExecuteDecevalSP' OR l.`Descripcion` LIKE '%ObtenerInformacionGirador_Pagare%' THEN '4a. SP Client_SP_ObtenerInformacionGirador_Pagare' END,
                        CASE WHEN l.`Metodo` = 'SavePdfAsync' AND l.`Descripcion` LIKE '%already exists%' THEN '2e. ALERTA: Archivo Duplicado (SavePdfAsync Bloqueado)'
                        WHEN l.`Metodo` = 'GetSignedFiles' AND l.`Descripcion` LIKE '%encontrados 0%' THEN '2a. ALERTA: Asincrona Bizagi Detenida (0 Documentos)' END,
                        CASE WHEN l.`Metodo` IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult') THEN '1f. Homologacion Estado Biometrico'
                        WHEN l.`Metodo` IN ('GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync') THEN '2b. Extraccion Argumentos PDF'
                        WHEN l.`Metodo` = 'FillDocumentsAsync' AND l.`Descripcion` LIKE '%pagare%' THEN '4d. Sincronizacion Pagare Deceval'
                        WHEN l.`Metodo` IN ('FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields') THEN '2c. Generacion y Llenado de PDF'
                        WHEN l.`Metodo` = 'SavePdfAsync' THEN '2d. Guardado de Archivos en Servidor'
                        WHEN l.`Metodo` IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'SingDocuments') THEN '3a. Firma Digital en WsSing'
                        WHEN l.`Metodo` IN ('RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') THEN '3b. Reintentos de Firma WsSing'
                        WHEN l.`Metodo` IN ('CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync') THEN '4b. Creacion de Pagare Deceval'
                        WHEN l.`Metodo` IN ('DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync') THEN '4c. Firma de Pagare Deceval'
                        WHEN l.`Metodo` IN ('NegotiableDocsAsync', 'HandleNewlyCreated') THEN '4d. Sincronizacion Pagare Deceval' END,
                        CASE WHEN l.`Metodo` IN ('GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil') OR l.`Descripcion` LIKE '%APIAgilSOA%' THEN '5a. Metodo GetInfoFromAgil (APIAgilSOA)'
                        WHEN l.`Metodo` IN ('GetDocumentsByProduct', 'GetSignedFiles') THEN '2a. Consulta de Estructuras Core (Bizagi)'
                        WHEN l.`Metodo` IN ('SendStateToAgil', 'HandleReportingProcess', 'SendFinalState', 'HandleResponse', 'SaveDetails', 'ReportOriginator', 'Método desconocido') THEN '5b. Reporte de Estado Final Bizagi'
                        WHEN l.`Metodo` IN ('SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') THEN '5c. Envio de Correo Notificacion'
                        WHEN l.`Metodo` IN ('Initializate', 'SavePendingSignature', 'CreateSingDetail') THEN '6a. Apertura del proceso de firma'
                        WHEN l.`Metodo` IN ('UpdateStateAsync', 'SingDocumentProcess') THEN '6b. Guardado de Detalles'
                        WHEN l.`Metodo` IN ('UpdateSignatureStateAsync', 'UpdateSignatures') THEN '6c. Transicion Estados Firma'
                        WHEN l.`Metodo` IN ('ProcessRetry', 'ExecuteRetryProcess') THEN '6d. Orquestador de Limpieza'
                        WHEN l.`Descripcion` LIKE '%Biometria%' OR l.`Descripcion` LIKE '%BiometricState%' THEN '1f. Homologacion Estado Biometrico'
                        WHEN l.`Descripcion` LIKE '%PDF%' OR l.`Descripcion` LIKE '%Archivo creado%' OR l.`Descripcion` LIKE '%argumentos%' THEN '2c. Generacion y Llenado de PDF'
                        WHEN l.`Descripcion` LIKE '%WsSing%' OR l.`Descripcion` LIKE '%procesarPlantillaAsync%' THEN '3a. Firma Digital en WsSing'
                        WHEN l.`Descripcion` LIKE '%Deceval%' OR l.`Descripcion` LIKE '%pagare%' OR l.`Descripcion` LIKE '%Girador%' THEN '4c. Firma de Pagare Deceval'
                        WHEN l.`Descripcion` LIKE '%Agil%' OR l.`Descripcion` LIKE '%Bizagi%' OR l.`Descripcion` LIKE '%reporte%' THEN '5b. Reporte de Estado Final Bizagi'
                        WHEN l.`Descripcion` LIKE '%correo%' OR l.`Descripcion` LIKE '%notificacion%' THEN '5c. Envio de Correo Notificacion'
                        ELSE '6b. Auditoria y Guardado de Detalles' END
                    ) AS Macro_Flujo_Negocio,
                    CASE
                        WHEN CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%already exists%' THEN 0
                        WHEN CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%Timeout of 600 seconds%'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%TimeoutException%'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%HttpClient.Timeout%' THEN 2
                        WHEN CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '% Error %'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE 'Error %'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '% Fallo %'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE 'Fallo %'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%Exception%' THEN 1
                        ELSE 0
                    END AS ErrorCode,
                    CASE
                        WHEN CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%already exists%' THEN 0
                        WHEN CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%Timeout of 600 seconds%'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%TimeoutException%'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%HttpClient.Timeout%'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '% Error %'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE 'Error %'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '% Fallo %'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE 'Fallo %'
                          OR CONCAT_WS(' ', l.`Descripcion`, l.`Adicional`, l.`Rs`) LIKE '%Exception%' THEN 1
                        ELSE 0
                    END AS EsError
                FROM LogMotorFirma.Log l
                WHERE l.`Fecha` >= CURDATE()
                  AND l.`Documento` IS NOT NULL AND l.`Documento` <> ''
                  AND l.`Documento` REGEXP '^[0-9]+$'
                  AND CAST(l.`Documento` AS UNSIGNED) > 50000
                  AND l.`Metodo` NOT LIKE 'GetPendingSignatures%'
            ) AS RawData
            ORDER BY IdProceso ASC, Fecha ASC
            LIMIT 18446744073709551615
        ) AS SortedData,
        (SELECT @prev_id := '', @prev_flujo := '', @prev_fecha := '1970-01-01 00:00:00') AS vars
    ) AS Layer2
    GROUP BY DiaProceso, IdProceso, Macro_Flujo_Negocio
) AS Layer3
GROUP BY DiaProceso, Macro_Flujo_Negocio
ORDER BY Macro_Flujo_Negocio ASC;
    """

    sql_p90 = """
    SELECT 
        ROUND(MIN(CASE WHEN row_num >= 0.90 * total_rows THEN Duracion_Minutos END), 2) AS P90_Firma_Minutos,
        ROUND(MIN(CASE WHEN row_num > 0.90 * total_rows THEN Duracion_Minutos END), 2) AS Min_Tiempo_Lentos,
        ROUND(MAX(CASE WHEN row_num > 0.90 * total_rows THEN Duracion_Minutos END), 2) AS Max_Tiempo_Lentos,
        SUM(CASE WHEN row_num > 0.90 * total_rows THEN 1 ELSE 0 END) AS Cantidad_Lentos,
        SUM(CASE WHEN row_num > 0.90 * total_rows AND Tuvo_Error = 1 THEN 1 ELSE 0 END) AS Errores_En_Lentos,
        MAX(total_rows) AS Total_Tramites_Exitosos,
        -- 🟢 NUEVO: Extraemos la lista exacta de IDs que fueron lentos y tuvieron errores
        GROUP_CONCAT(CASE WHEN row_num > 0.90 * total_rows AND Tuvo_Error = 1 THEN Documento END SEPARATOR ', ') AS IDs_Errores_Lentos
    FROM (
        SELECT 
            Documento, -- 🟢 Subimos el Documento para poder concatenarlo arriba
            Duracion_Minutos,
            Tuvo_Error,
            @row_num := @row_num + 1 AS row_num
        FROM (
            SELECT 
                l.Documento,
                ROUND(TIMESTAMPDIFF(SECOND, 
                    COALESCE(
                        MIN(CASE WHEN l.Metodo IN ('SingDocuments') OR l.Descripcion LIKE '%Inicia proceso de Firma%' THEN l.Fecha END),
                        MIN(CASE WHEN l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%' THEN l.Fecha END)
                    ),
                    MIN(CASE WHEN l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%' THEN l.Fecha END)
                ) / 60.0, 2) AS Duracion_Minutos,
                MAX(CASE
                    WHEN (
                        CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout of 600 seconds%' OR 
                        CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%TimeoutException%' OR 
                        CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%HttpClient.Timeout%' OR 
                        CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Error %' OR 
                        CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Error %' OR 
                        CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '% Fallo %' OR 
                        CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE 'Fallo %' OR 
                        CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%'
                    )
                    -- 🟢 REGLA DECEVAL: Ignoramos el error si Deceval fue exitoso al final
                    AND NOT (
                        (
                            l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') 
                            OR l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' 
                            OR l.Descripcion LIKE '%Deceval%' 
                            OR l.Descripcion LIKE '%pagare%'
                        )
                        AND EXISTS (
                            SELECT 1 
                            FROM LogMotorFirma.Log l2 
                            WHERE l2.Documento = l.Documento 
                              AND l2.Fecha >= CURDATE() 
                              AND l2.Descripcion LIKE '%Proceso de firma Deceval exitoso%'
                        )
                    ) THEN 1
                    WHEN l.Descripcion LIKE '%Antiguo : 1000%' THEN 1 
                    ELSE 0
                END) AS Tuvo_Error
            FROM LogMotorFirma.Log l
            WHERE l.Fecha >= DATE_SUB(CURDATE(), INTERVAL 3 DAY)
              AND l.Documento IS NOT NULL AND l.Documento <> ''
              AND l.Documento REGEXP '^[0-9]+$' 
              AND CAST(l.Documento AS UNSIGNED) > 30000 
            GROUP BY l.Documento
            HAVING MAX(CASE WHEN l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%' AND l.Fecha >= CURDATE() THEN 1 ELSE 0 END) = 1
            ORDER BY Duracion_Minutos ASC
        ) AS OrderedData,
        (SELECT @row_num := 0) AS r
    ) AS RankedData
    CROSS JOIN (
        SELECT COUNT(*) AS total_rows
        FROM (
            SELECT Documento
            FROM LogMotorFirma.Log
            WHERE Fecha >= DATE_SUB(CURDATE(), INTERVAL 3 DAY)
              AND Documento IS NOT NULL AND Documento <> ''
              AND Documento REGEXP '^[0-9]+$' 
              AND CAST(Documento AS UNSIGNED) > 30000 
            GROUP BY Documento
            HAVING MAX(CASE WHEN Descripcion LIKE '%Nuevo estado de la solicitud: 1000%' AND Fecha >= CURDATE() THEN 1 ELSE 0 END) = 1
        ) AS BaseCount
    ) AS TotalData;
    """

    sql_hora_pico = """
    SELECT 
    CONCAT(LPAD(HOUR(Hora_Primer_Error), 2, '0'), ':00 - ', LPAD(HOUR(Hora_Primer_Error), 2, '0'), ':59') AS Franja_Horaria,
    -- 🟢 ALIAS RECTIFICADO: Mantiene el nombre exacto para n8n
    COUNT(*) AS Volumen_Procesos_Reales,
    ROUND((COUNT(*) * 100.0) / NULLIF((
        -- 🔴 DENOMINADOR: Total de documentos únicos que sufrieron fallos reales hoy
        SELECT COUNT(DISTINCT l_den.Documento) 
        FROM LogMotorFirma.Log l_den
        LEFT JOIN (
            SELECT 
                Documento,
                MAX(CASE WHEN Descripcion LIKE '%Proceso de firma Deceval exitoso%' THEN 1 ELSE 0 END) AS Deceval_Exitoso
            FROM LogMotorFirma.Log
            WHERE Fecha >= CURDATE()
            GROUP BY Documento
        ) AS m_den ON l_den.Documento = m_den.Documento
        WHERE l_den.Fecha >= CURDATE() 
          AND l_den.Documento IS NOT NULL AND l_den.Documento <> '' 
          AND l_den.Documento REGEXP '^[0-9]+$' 
          AND CAST(l_den.Documento AS UNSIGNED) > 30000
          AND l_den.Metodo NOT LIKE 'GetPendingSignatures%'
          -- 🎯 FILTRO DE ALTA PRECISIÓN (Denominador)
          AND (
              CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) LIKE '%Exception%'
              OR CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) LIKE '%Timeout%'
              OR (
                  (
                      CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) LIKE '%Error %' 
                      OR CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) LIKE '%Error:%'
                      OR CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) LIKE '%Fallo%'
                  )
                  AND CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) NOT LIKE '%error: 0%'
                  AND CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) NOT LIKE '%with error: 0%'
              )
          )
          -- 🧼 EXCLUSIONES DE ÁGIL
          AND CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) NOT LIKE '%already exists%'
          AND CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) NOT LIKE '%There is an error in XML document%'
          AND CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) NOT LIKE '%Error durante el proceso de validacion de response Agil%'
          -- 🛑 REGLA DEL PERDÓN DECEVAL
          AND NOT (
              CONCAT_WS(' ', l_den.Descripcion, l_den.Adicional, l_den.Rs) LIKE '%Error durante la verificacion de Pagare%'
              AND COALESCE(m_den.Deceval_Exitoso, 0) = 1
          )
    ), 0), 2) AS Porcentaje -- 🟢 ALIAS RECTIFICADO: Mantiene el nombre exacto para n8n
FROM (
    --  NUMERADOR: Captura el primer fallo real por radicado (Sin ambigüedad)
    SELECT 
        l.Documento, 
        MIN(l.Fecha) AS Hora_Primer_Error
    FROM LogMotorFirma.Log l
    LEFT JOIN (
        SELECT 
            Documento,
            MAX(CASE WHEN Descripcion LIKE '%Proceso de firma Deceval exitoso%' THEN 1 ELSE 0 END) AS Deceval_Exitoso
        FROM LogMotorFirma.Log
        WHERE Fecha >= CURDATE()
        GROUP BY Documento
    ) AS m ON l.Documento = m.Documento
    WHERE l.Fecha >= CURDATE()
      AND l.Documento IS NOT NULL AND l.Documento <> ''
      AND l.Documento REGEXP '^[0-9]+$' 
      AND CAST(l.Documento AS UNSIGNED) > 30000 
      AND l.Metodo NOT LIKE 'GetPendingSignatures%'
      --  FILTRO DE ALTA PRECISIÓN (Numerador)
      AND (
          CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%'
          OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout%'
          OR (
              (
                  CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error %' 
                  OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error:%'
                  OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Fallo%'
              )
              AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%error: 0%'
              AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%with error: 0%'
              AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%already exists%'
          )
      )
      --  EXCLUSIONES DE ÁGIL
      
      AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%There is an error in XML document%'
      AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error durante el proceso de validacion de response Agil%'
      --  REGLA DEL PERDÓN DECEVAL
      AND NOT (
          CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error durante la verificacion de Pagare%'
          AND COALESCE(m.Deceval_Exitoso, 0) = 1
      )
    GROUP BY l.Documento
) AS T
GROUP BY HOUR(Hora_Primer_Error)
ORDER BY HOUR(Hora_Primer_Error) ASC;
    """
    
    sql_desgloce_hora_pico = """
    SELECT 
    l.Documento AS Radicado_Id,
    CONCAT(LPAD(HOUR(MIN(l.Fecha)), 2, '0'), ':00 - ', LPAD(HOUR(MIN(l.Fecha)), 2, '0'), ':59') AS Franja_Horaria,
    MIN(l.Fecha) AS Hora_Exacta_Primer_Fallo,
    -- Concatena los métodos únicos si el mismo radicado falló en más de uno
    GROUP_CONCAT(DISTINCT l.Metodo SEPARATOR ' | ') AS Metodos_Con_Fallo,
    -- Trae el extracto del primer error reportado
    LEFT(CONCAT_WS(' | ', l.Descripcion, l.Adicional, l.Rs), 250) AS Extracto_Log_Tecnico
FROM LogMotorFirma.Log l
LEFT JOIN (
    SELECT 
        Documento,
        MAX(CASE WHEN Descripcion LIKE '%Proceso de firma Deceval exitoso%' THEN 1 ELSE 0 END) AS Deceval_Exitoso
    FROM LogMotorFirma.Log
    WHERE Fecha >= CURDATE()
    GROUP BY Documento
) AS m ON l.Documento = m.Documento
WHERE l.Fecha >= CURDATE()
  AND l.Documento IS NOT NULL AND l.Documento <> ''
  AND l.Documento REGEXP '^[0-9]+$' 
  AND CAST(l.Documento AS UNSIGNED) > 30000 
  AND l.Metodo NOT LIKE 'GetPendingSignatures%'
  -- 🎯 Filtro de errores de alta precisión
  AND (
      l.Descripcion LIKE '%Exception%'
      OR l.Descripcion LIKE '%Timeout%'
      OR (
          (
              CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error %' 
              OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error:%'
              OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Fallo%'
          )
          AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%error: 0%'
          AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%with error: 0%'
      )
  )
  -- 🧼 Exclusiones de ruidos controlados
  AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%already exists%'
  AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%There is an error in XML document%'
  AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error durante el proceso de validacion de response Agil%'
  -- 🛑 Regla del perdón de Deceval
  AND NOT (
      CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error durante la verificacion de Pagare%'
      AND COALESCE(m.Deceval_Exitoso, 0) = 1
  )
-- 🟢 EL CAMBIO CLAVE: Agrupamos por radicado para consolidar duplicados
GROUP BY l.Documento
ORDER BY Hora_Exacta_Primer_Fallo ASC;
    """

    # 4. SQL del Top 3 Errores
    sql_top_errores = """
    SELECT 
        Metodo AS Falla_En_Metodo,
        CASE 
            WHEN CONCAT_WS(' ', Descripcion, Adicional, Rs) LIKE '%Timeout%' THEN 'Error de Timeout (Servidor/Red)'
            WHEN CONCAT_WS(' ', Descripcion, Adicional, Rs) LIKE '%NullReference%' THEN 'Referencia Nula en Código'
            WHEN CONCAT_WS(' ', Descripcion, Adicional, Rs) LIKE '%Deceval%' THEN 'Fallo en Integración Deceval'
            WHEN CONCAT_WS(' ', Descripcion, Adicional, Rs) LIKE '%Bizagi%' THEN 'Fallo en Integración Bizagi'
            ELSE SUBSTRING(Descripcion, 1, 50)
        END AS Causa_Raiz,
        COUNT(*) AS Frecuencia
    FROM LogMotorFirma.Log
    WHERE Fecha >= CURDATE()
      AND (
          CONCAT_WS(' ', Descripcion, Adicional, Rs) LIKE '%Error%' 
          OR CONCAT_WS(' ', Descripcion, Adicional, Rs) LIKE '%Fallo%' 
          OR CONCAT_WS(' ', Descripcion, Adicional, Rs) LIKE '%Exception%'
          OR CONCAT_WS(' ', Descripcion, Adicional, Rs) LIKE '%Timeout%'
      )
    GROUP BY Falla_En_Metodo, Causa_Raiz
    ORDER BY Frecuencia DESC
    LIMIT 3;
    """

    sql_service_time = """ 
    SELECT 
    Macro_Flujo_Negocio,
    -- Forzamos a 0 las columnas operacionales inferiores para los SPs filtrados
    0 AS `0_a_1_Minuto`,
    0 AS `1_a_2_Minutos`,
    0 AS `2_a_3_Minutos`,
    SUM(CASE WHEN DuracionMinutos > 3.0 AND DuracionMinutos <= 5.0 THEN 1 ELSE 0 END) AS `3_a_5_Minutos`,
    SUM(CASE WHEN DuracionMinutos > 5.0 THEN 1 ELSE 0 END) AS `Mas_de_5_Minutos`,
    SUM(CASE WHEN ErroresEnProceso > 0 THEN 1 ELSE 0 END) AS Procesos_Con_Error,
    COUNT(*) AS Total_Ejecuciones
FROM (
    SELECT DiaProceso, IdProceso, Macro_Flujo_Negocio, 
           SUM(CASE WHEN DeltaSeconds <= 1800 THEN DeltaSeconds ELSE 0 END) / 60.0 AS DuracionMinutos,
           SUM(EsError) AS ErroresEnProceso
    FROM (
        SELECT DiaProceso, IdProceso, Macro_Flujo_Negocio, EsError,
               IF(@prev_id = IdProceso AND @prev_flujo = Macro_Flujo_Negocio, TIMESTAMPDIFF(SECOND, @prev_fecha, Fecha), 0) AS DeltaSeconds, 
               @prev_id := IdProceso AS set_id, 
               @prev_flujo := Macro_Flujo_Negocio AS set_flujo, 
               @prev_fecha := Fecha AS set_fecha
        FROM (
            SELECT * FROM (
                SELECT DATE(l.`Fecha`) AS DiaProceso, l.`Documento` AS IdProceso, l.`Fecha`,
                    CASE 
                        WHEN l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%Parte1%' THEN 'SP Client_SP_GetInfoDocBiometriaParte1'
                        WHEN l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%Parte2%' THEN 'SP Client_SP_GetInfoDocBiometriaParte2'
                        WHEN l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%Parte3%' THEN 'SP Client_SP_GetInfoDocBiometriaParte3'
                        WHEN l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%Parte4VC%' THEN 'SP Client_SP_GetInfoDocBiometriaParte4VC'
                        WHEN (l.`Metodo` = 'ExecuteBiometricsSP' AND l.`Descripcion` LIKE '%GetDataClient%') 
                          OR l.`Metodo` IN ('ExecuteSpBiometrics', 'GetClientBiometricData') THEN 'SP Client_SP_GetDataClientBiometria'
                        WHEN l.`Metodo` = 'ExecuteDecevalSP' OR l.`Descripcion` LIKE '%ObtenerInformacionGirador_Pagare%' THEN 'SP Client_SP_ObtenerInformacionGirador_Pagare'
                        WHEN l.`Metodo` = 'SavePdfAsync' AND l.`Descripcion` LIKE '%already exists%' THEN 'ALERTA: Archivo Duplicado (SavePdfAsync Bloqueado)'
                        WHEN l.`Metodo` = 'GetSignedFiles' AND l.`Descripcion` LIKE '%encontrados 0%' THEN 'ALERTA: Asincrona Bizagi Detenida (0 Documentos)'
                    END AS Macro_Flujo_Negocio,
                    CASE 
                        WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error%' 
                          OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%'
                          OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Fallo%'
                          OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout%' THEN 1 
                        ELSE 0 
                    END AS EsError
                FROM LogMotorFirma.Log l
                WHERE l.`Fecha` >= CURDATE() 
                  AND l.`Documento` IS NOT NULL AND l.`Documento` <> ''
                  AND l.`Documento` REGEXP '^[0-9]+$' 
                  AND CAST(l.`Documento` AS UNSIGNED) > 50000 
                  AND l.`Metodo` NOT LIKE 'GetPendingSignatures%'
            ) AS RawData
            WHERE Macro_Flujo_Negocio IS NOT NULL
            ORDER BY IdProceso ASC, Fecha ASC
            LIMIT 18446744073709551615
        ) AS SortedData,
        (SELECT @prev_id := '', @prev_flujo := '', @prev_fecha := '1970-01-01 00:00:00') AS vars
    ) AS Layer2
    GROUP BY DiaProceso, IdProceso, Macro_Flujo_Negocio
) AS Layer3
WHERE 
    -- Regla de descarte de duplicados cruzados de Bizagi
    NOT (
        Macro_Flujo_Negocio = 'ALERTA: Asincrona Bizagi Detenida (0 Documentos)'
        AND IdProceso IN (
            SELECT Documento 
            FROM LogMotorFirma.Log 
            WHERE Fecha >= CURDATE() 
              AND Metodo = 'SavePdfAsync' 
              AND Descripcion LIKE '%already exists%'
        )
    )
    -- 🎯 REGLA INYECTADA DE EXCLUSIÓN INTELIGENTE:
    -- Deja pasar si el SP demoró más de 3 minutos O si el registro es una Alerta directa del sistema
    AND (DuracionMinutos > 3.00 OR Macro_Flujo_Negocio LIKE 'ALERTA:%')
GROUP BY Macro_Flujo_Negocio
ORDER BY Macro_Flujo_Negocio ASC;
    """
    
    sql_errores_services = """
SELECT
    IdProceso AS IdSolicitud,
    Macro_Flujo_Negocio AS Causa_Revision,
    Etapa_Negocio,
    ROUND(DuracionMinutos, 2) AS Duracion_Minutos,
    DATE_FORMAT(HoraInicio, '%H:%i:%s') AS Hora_Inicio,
    DATE_FORMAT(HoraFin, '%H:%i:%s') AS Hora_Fin,
    CASE WHEN ErroresEnProceso > 0 THEN MensajeError ELSE 'No' END AS Hubo_Error_Tecnico
FROM (
    SELECT
        DiaProceso,
        IdProceso,
        Macro_Flujo_Negocio,
        Etapa_Negocio,
        TIMESTAMPDIFF(SECOND, MIN(Fecha), MAX(Fecha)) / 60.0 AS DuracionMinutos,
        SUM(EsError) AS ErroresEnProceso,
        MAX(CASE WHEN EsError = 1 THEN MensajeError ELSE NULL END) AS MensajeError,
        MIN(Fecha) AS HoraInicio,
        MAX(Fecha) AS HoraFin
    FROM (
        SELECT
            DATE(l.Fecha) AS DiaProceso,
            l.Documento AS IdProceso,
            l.Fecha,
            CASE
                WHEN l.Metodo = 'SavePendingSignature' THEN 'SavePendingSignature'
                WHEN l.Metodo = 'ExecuteBiometricsSP' AND l.Descripcion LIKE '%Parte1%' THEN 'SP_GetInfoDocBiometriaParte1'
                WHEN l.Metodo = 'ExecuteBiometricsSP' AND l.Descripcion LIKE '%Parte2%' THEN 'SP_GetInfoDocBiometriaParte2'
                WHEN l.Metodo = 'ExecuteBiometricsSP' AND l.Descripcion LIKE '%Parte3%' THEN 'SP_GetInfoDocBiometriaParte3'
                WHEN l.Metodo = 'ExecuteBiometricsSP' AND l.Descripcion LIKE '%Parte4VC%' THEN 'SP_GetInfoDocBiometriaParte4VC'
                WHEN l.Metodo IN ('ExecuteSpBiometrics', 'GetClientBiometricData') THEN 'SP_GetDataClientBiometria'
                WHEN l.Metodo = 'ExecuteBiometricsSP' AND l.Descripcion LIKE '%GetDataClient%' THEN 'SP_GetDataClientBiometria'
                WHEN l.Metodo = 'SingDocuments' THEN 'SingDocuments'
                WHEN l.Metodo = 'ValidateCurrentState' THEN 'ValidateCurrentState'
                WHEN l.Metodo = 'ValidateBiometricProcess' THEN 'ValidateBiometricProcess'
                WHEN l.Metodo = 'ProcessBioResult' THEN 'ProcessBioResult'
                WHEN l.Metodo = 'WsSingSingProcess' THEN 'WsSingSingProcess'
                WHEN l.Metodo = 'SingPdfWsSingAsync' THEN 'SingPdfWsSingAsync'
                WHEN l.Metodo = 'EditPdfAndConvertToBase64Async' THEN 'EditPdfAndConvertToBase64Async'
                WHEN l.Metodo = 'GetArgumentsFromPDF' THEN 'GetArgumentsFromPDF'
                WHEN l.Metodo = 'GetArgumentsByTemplate' THEN 'GetArgumentsByTemplate'
                WHEN l.Metodo = 'GetArgumentsAsync' THEN 'GetArgumentsAsync'
                WHEN l.Metodo = 'ProcessTemplatePdfAsync' THEN 'ProcessTemplatePdfAsync'
                WHEN l.Metodo = 'SavePdfAsync' AND l.Descripcion NOT LIKE '%already exists%' THEN 'SavePdfAsync'
                WHEN l.Metodo = 'SavePdfAsync' AND l.Descripcion LIKE '%already exists%' THEN 'ALERTA: Archivo Duplicado (Generado debido a que el flujo fue devuelto)'
                WHEN l.Metodo = 'ExecuteDecevalSP' THEN 'SP_ObtenerInformacionGirador_Pagare'
                WHEN l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' THEN 'SP_ObtenerInformacionGirador_Pagare'
                WHEN l.Metodo IN ('GetDecevalInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInfoFromTcGarantizadaAsync') THEN 'GetDecevalInfoFromAgil'
                WHEN l.Metodo = 'CreatePayNoteAsync' THEN 'CreatePayNoteAsync'
                WHEN l.Metodo = 'SingPdfDecevalAsync' THEN 'SingPdfDecevalAsync'
                WHEN l.Metodo IN ('DecevalSingProcess', 'NegotiableDocsAsync', 'NonNegotiablesDocsAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'SingDocumentDecevalAsync', 'HandleExistingPayNote', 'FillDocumentsAsync') THEN 'DecevalSingProcess (soporte)'
                WHEN l.Metodo IN ('SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') THEN 'SendMailAsync'
                WHEN l.Metodo IN ('ReportOriginator', 'HandleReportingProcess') THEN 'ReportOriginator'
                WHEN l.Metodo = 'GetSignedFiles' AND l.Descripcion LIKE '%encontrados 0%' THEN 'ALERTA: Asincrona Bizagi Detenida (0 Documentos)'
                ELSE NULL
            END AS Macro_Flujo_Negocio,
            CASE
                WHEN l.Metodo = 'SavePendingSignature' THEN '1. Agil registra solicitud'
                WHEN l.Metodo IN ('GetDocumentsByProduct','GetClientBiometricData','GetArgumentsFromPDF','GetArgumentsByTemplate','GetArgumentsAsync','FillDocumentsAsync','ProcessTemplatePdfAsync','ExecuteBiometricsSP','ExecuteSpBiometrics','GetDecevalInfoFromAgil','EditPdfAndConvertToBase64Async','SingDocuments','GetDecevalInformationFromAgil','GetDecevalInfoFromTcGarantizadaAsync') THEN '2. App consulta documentos'
                WHEN l.Descripcion LIKE '%APIAgilSOA%' THEN '2. App consulta documentos'
                WHEN l.Metodo IN ('ValidateBiometricProcess','ProcessBioResult','GetBiometricsResult','Initializate','CreateSingDetail','ValidateCurrentState') THEN '3. Biometria y firma inicial'
                WHEN l.Descripcion LIKE '%BiometricState%' THEN '3. Biometria y firma inicial'
                WHEN l.Metodo IN ('WsSingSingProcess','SingPdfWsSingAsync','MapWsSingRequestAsync','RetrySingInWsSing') THEN '4. Firma digital WsSing'
                WHEN l.Descripcion LIKE '%WsSing%' THEN '4. Firma digital WsSing'
                WHEN l.Metodo IN ('ExecuteDecevalSP','CreatePayNoteAsync','GeneratePayNote','DecevalSingProcess','SingPdfDecevalAsync','NegotiableDocsAsync','HandleExistingPayNote','FillDocumentsAsync','SingDocumentDecevalAsync','GetPayNoteAsync') THEN '5. Firma pagare Deceval'
                WHEN l.Descripcion LIKE '%Deceval%' THEN '5. Firma pagare Deceval'
                WHEN l.Descripcion LIKE '%ObtenerInformacionGirador_Pagare%' THEN '5. Firma pagare Deceval'
                WHEN l.Metodo IN ('SavePdfAsync','ReportOriginator','SendMailAsync','SendMail','HandleReportingProcess','GetSignedFiles','SendEmailIfPendingSignatureExists') THEN '6. Almacenamiento y reporte'
                WHEN l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%' THEN '6. Almacenamiento y reporte'
                ELSE '0. Soporte interno'
            END AS Etapa_Negocio,
            CASE
                WHEN (CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error%'
                    OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%'
                    OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Fallo%'
                    OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout%')
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%SDL.SE.0000%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Exitoso%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%exitosamente%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Todos los giradores se procesaron correctamente%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error en reporte solicitud%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error en proceso de reporte de estado a Agil%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error Error durante el proceso de validacion de response Agil%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%There is an error in XML docu%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error durante la verificacion de Pagare%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error consultando en el servicio de consulta pagare Deceval%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error consultando en el servicio de APIAgilSOA%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%HttpClient.Timeout%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error procesando los argumentos%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%servicio de WsSing retorn% documento vac%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Total pdf fields with error: 0%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Total JSON:%'
                THEN 1
                ELSE 0
            END AS EsError,
            CASE
                WHEN (CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Error%'
                    OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Exception%'
                    OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Fallo%'
                    OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) LIKE '%Timeout%')
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%SDL.SE.0000%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Exitoso%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%exitosamente%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Todos los giradores se procesaron correctamente%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error en reporte solicitud%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error en proceso de reporte de estado a Agil%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error Error durante el proceso de validacion de response Agil%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%There is an error in XML docu%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error durante la verificacion de Pagare%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error consultando en el servicio de consulta pagare Deceval%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error consultando en el servicio de APIAgilSOA%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%HttpClient.Timeout%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Error procesando los argumentos%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Total pdf fields with error: 0%'
                AND CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) NOT LIKE '%Total JSON:%'
                THEN LEFT(CONCAT_WS(' | ', NULLIF(TRIM(l.Descripcion),''), NULLIF(TRIM(l.Adicional),'')), 120)
                ELSE NULL
            END AS MensajeError
        FROM LogMotorFirma.Log l
        WHERE l.Fecha >= CURDATE()
          AND l.Documento IS NOT NULL
          AND l.Documento <> ''
          AND l.Documento REGEXP '^[0-9]+$'
          AND CAST(l.Documento AS UNSIGNED) > 50000
    ) AS RawData
    WHERE Macro_Flujo_Negocio IS NOT NULL
    GROUP BY DiaProceso, IdProceso, Macro_Flujo_Negocio, Etapa_Negocio
) AS CasosAgrupados
WHERE
    (
        Macro_Flujo_Negocio LIKE 'ALERTA:%'
        AND NOT (
            Macro_Flujo_Negocio = 'ALERTA: Asincrona Bizagi Detenida (0 Documentos)'
            AND IdProceso IN (
                SELECT Documento FROM LogMotorFirma.Log
                WHERE Fecha >= CURDATE()
                  AND Metodo = 'SavePdfAsync'
                  AND Descripcion LIKE '%already exists%'
            )
        )
    )
    OR (Macro_Flujo_Negocio LIKE '%SP_%' AND DuracionMinutos > 3.0)
    OR Macro_Flujo_Negocio NOT LIKE 'ALERTA:%'
ORDER BY Etapa_Negocio ASC, Macro_Flujo_Negocio ASC, DuracionMinutos DESC;  -- 🆕 ordenar por etapa primero
"""
    try:
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                # Ejecutamos las 4 consultas
                cur.execute(sql_principal)
                reporte_sla = cur.fetchall()

                cur.execute(sql_p90)
                resultado_p90 = cur.fetchall()

                cur.execute(sql_hora_pico)
                resultado_pico = cur.fetchall()

                cur.execute(sql_desgloce_hora_pico)
                resultado_desgloce_pico = cur.fetchall()
                cur.execute(sql_top_errores)
                resultado_top = cur.fetchall()
                
                cur.execute(sql_service_time)
                resultado_service_time = cur.fetchall()
                
                cur.execute(sql_etapas)
                resultado_etapas = cur.fetchall()
                
                cur.execute(sql_errores_etapa)
                resultado_errores_etapa = cur.fetchall()

                cur.execute(sql_tiempo_etapas)
                resultado_tiempo_etapas = cur.fetchall()
                
                cur.execute(sql_lentos_detalle)
                resultado_lentos_detalle = cur.fetchall()

                cur.execute(sql_Cliente_consulta_documentos)
                resultado_cliente_consulta_documentos = cur.fetchall()
                
                cur.execute(sql_Biometria)
                resultado_biometria = cur.fetchall()

                cur.execute(sql_WsSing)
                resultado_ws_sing = cur.fetchall()
                
                cur.execute(sql_Deceval)
                resultado_deceval = cur.fetchall()
                
                cur.execute(sql_Agil)
                resultado_agil = cur.fetchall()
                
                cur.execute(sql_errores_services)
                resultado_errores_services = cur.fetchall()

        # Empaquetamos todo en el JSON final
        return jsonify({
            "Reporte_SLA_Hoy": reporte_sla,
            "Service_Time": resultado_service_time,
            "Etapas": resultado_etapas,
            "Errores_Por_Etapa": resultado_errores_etapa,
            "Tiempo_Por_Etapa": resultado_tiempo_etapas,
            "Lentos_Detalle": resultado_lentos_detalle,
            "Cliente_Consulta_Documentos": resultado_cliente_consulta_documentos,
            "Biometria": resultado_biometria,
            "WsSing": resultado_ws_sing,
            "Deceval": resultado_deceval,
            "Agil": resultado_agil,
            "Errores_Services": resultado_errores_services,
            "Insights": {
                "P90": resultado_p90[0] if resultado_p90 else None,
                "Hora_Pico": resultado_pico, # 🟢 AHORA SÍ PASA LA LISTA COMPLETA
                "Desgloce_Hora_Pico": resultado_desgloce_pico
            }
        })
    except Exception as e:
        return jsonify({"error": f"Error BD: {str(e)}"}), 500

# ==========================================
# 🔍 ENDPOINT 2: AUDITORÍA CRUZADA (POST)
# ==========================================
@app.route("/auditoria-cruzada", methods=["POST"])
def auditoria_cruzada():
    data = request.json or {}
    documentos = data.get("documentos", [])
    
    # Si no nos envían documentos, retornamos lista vacía sin tocar la BD
    if not documentos:
        return jsonify([])

    # Protegemos contra inyecciones SQL armando los placeholders %s dinámicamente
    doc_list = [str(d) for d in documentos]
    placeholders = ', '.join(['%s'] * len(doc_list))

    
# ⚠️ CONSULTA SQL LIMPIA (Sin WITH ni ROW_NUMBER)
    sql_auditoria = f"""
    SELECT 
        l.Documento AS IdSolicitud,
        COALESCE(MIN(CASE WHEN l.Metodo != 'SavePendingSignature' THEN l.Fecha END), MIN(l.Fecha)) AS Hora_Inicio,
        COALESCE(MAX(CASE WHEN l.Metodo != 'SavePendingSignature' THEN l.Fecha END), MAX(l.Fecha)) AS Hora_Fin,
        
        MAX(CASE 
            WHEN LOWER(CONCAT_WS(' ', l.Adicional, l.Rs, l.Descripcion)) LIKE '%%"idcaso":%%' 
            THEN TRIM(REPLACE(REPLACE(REPLACE(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(LOWER(CONCAT_WS(' ', l.Adicional, l.Rs, l.Descripcion)), '"idcaso":', -1), ',', 1), '}}', ''), ']', ''), '"', ''), CHAR(92), ''))
            
            WHEN LOWER(CONCAT_WS(' ', l.Adicional, l.Rs, l.Descripcion)) LIKE '%%"biometricscaseid":%%' 
            THEN TRIM(REPLACE(REPLACE(REPLACE(REPLACE(SUBSTRING_INDEX(SUBSTRING_INDEX(LOWER(CONCAT_WS(' ', l.Adicional, l.Rs, l.Descripcion)), '"biometricscaseid":', -1), ',', 1), '}}', ''), ']', ''), '"', ''), CHAR(92), ''))
        END) AS IdCaso_Biometria,

        MAX(CASE 
            WHEN (l.Metodo IN ('SavePdfAsync', 'GetSignedFiles', 'SendStateToAgil', 'HandleReportingProcess', 'SendFinalState', 'HandleResponse', 'ReportOriginator', 'SendMailAsync', 'SendMail', 'SendEmailIfPendingSignatureExists') OR l.Descripcion LIKE '%%envio de correo%%' OR l.Descripcion LIKE '%%proceso de notificacion%%' OR l.Descripcion LIKE '%%Inicia proceso de guardar PDF%%' OR l.Descripcion LIKE '%%Nuevo estado de la solicitud: 1000%%') THEN '6. Almacenamiento PDF y reporte a ÁGIL'
            WHEN (l.Metodo IN ('ExecuteDecevalSP', 'CreatePayNoteAsync', 'GeneratePayNote', 'GetPayNoteAsync', 'DecevalSingProcess', 'SingPdfDecevalAsync', 'SingDocumentDecevalAsync', 'NegotiableDocsAsync', 'HandleNewlyCreated') OR l.Descripcion LIKE '%%ObtenerInformacionGirador_Pagare%%' OR l.Descripcion LIKE '%%Deceval%%' OR l.Descripcion LIKE '%%pagare%%') THEN '5. Firma Digital (Deceval)'
            WHEN (l.Metodo IN ('WsSingSingProcess', 'SingPdfWsSingAsync', 'MapWsSingRequestAsync', 'RetrySingInWsSing', 'MapRetryWsSingRequest', 'RetrySingPdfWsSing') OR l.Descripcion LIKE '%%WsSing%%') THEN '4. Firma Digital (WsSing)'
            WHEN l.Descripcion LIKE '%%Inicia proceso de Firma.%%' OR l.Descripcion LIKE 'Inicia proceso de Firma' OR l.Metodo IN ('ValidateBiometricProcess', 'ProcessBioResult', 'GetBiometricsResult', 'Initializate', 'CreateSingDetail') OR l.Descripcion LIKE '%%BiometricState%%' OR l.Descripcion LIKE '%%Biometria%%' THEN '3. Cliente INICIA proceso de firma y Biometría'
            WHEN l.Metodo IN ('ExecuteBiometricsSP', 'ExecuteSpBiometrics', 'GetClientBiometricData', 'GetInfoFromAgil', 'GetInformationFromAgil', 'GetDecevalInfoFromAgil', 'GetDecevalInformationFromAgil', 'GetArgumentsFromPDF', 'GetArgumentsByTemplate', 'GetArgumentsAsync', 'FillDocumentsAsync', 'ProcessTemplatePdfAsync', 'GetInfoToPdf', 'NonNegotiablesDocsAsync', 'DetermineListAndAddSoloFields', 'GetDocumentsByProduct') OR l.Descripcion LIKE '%%GetDataClient%%' OR l.Descripcion LIKE '%%APIAgilSOA%%' THEN '2. Cliente CONSULTA documentos'
            WHEN l.Metodo = 'SavePendingSignature' THEN '0. Cliente NO ha iniciado proceso de firma'
            ELSE '1. Transición / Actividad Inicial' 
        END) AS Etapa_Alcanzada_Logs,
        
        SUM(CASE
            WHEN CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%already exists%%' THEN 0
            WHEN CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%There is an error in XML document%%' THEN 0
            WHEN CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%Error durante el proceso de validacion de response Agil%%' THEN 0
            WHEN CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%Timeout of 600 seconds%%' OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%TimeoutException%%' OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%HttpClient.Timeout%%' THEN 1
            WHEN CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%% Error %%' OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE 'Error %%' OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%% Fallo %%' OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE 'Fallo %%' OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%Exception%%' THEN 1
            ELSE 0
        END) AS Total_Errores_Tecnicos,

        COALESCE(
            MAX(CASE WHEN CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%Timeout%%' THEN 'Timeout encontrado' END),
            MAX(CASE 
                WHEN (CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%Exception%%' OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%Fallo%%' OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%% Error %%')
                AND CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) NOT LIKE '%%There is an error in XML document%%'
                AND CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) NOT LIKE '%%Error durante el proceso de validacion de response Agil%%'
                THEN LEFT(CONCAT_WS(' | ', NULLIF(TRIM(l.Descripcion),''), NULLIF(TRIM(l.Adicional),'')), 200)
            END),
            'Inactividad del Cliente'
        ) AS Causa_Raiz,

        -- 🆕 MENSAJE REAL DEL ERROR
        COALESCE(
            MAX(CASE 
                WHEN CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%Timeout of 600 seconds%%'
                  OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%TimeoutException%%'
                  OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%HttpClient.Timeout%%'
                THEN LEFT(CONCAT_WS(' | ', NULLIF(TRIM(l.Descripcion),''), NULLIF(TRIM(l.Adicional),'')), 200)
            END),
            MAX(CASE 
                WHEN (CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%Exception%%'
                   OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%%Fallo%%'
                   OR CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) LIKE '%% Error %%')
                AND CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) NOT LIKE '%%already exists%%'
                AND CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) NOT LIKE '%%There is an error in XML document%%'
                AND CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) NOT LIKE '%%Error durante el proceso de validacion de response Agil%%'
                AND CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) NOT LIKE '%%Error consultando en el servicio de APIAgilSOA%%'
                AND CONVERT(CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs) USING utf8mb4) NOT LIKE '%%HttpClient.Timeout%%'
                THEN LEFT(CONCAT_WS(' | ', NULLIF(TRIM(l.Descripcion),''), NULLIF(TRIM(l.Adicional),'')), 200)
            END)
        ) AS Mensaje_Error_Tecnico,

        ROUND(GREATEST(TIMESTAMPDIFF(SECOND, 
            COALESCE(MIN(CASE WHEN l.Metodo != 'SavePendingSignature' THEN l.Fecha END), MIN(l.Fecha)), 
            COALESCE(MAX(CASE WHEN l.Metodo != 'SavePendingSignature' THEN l.Fecha END), MAX(l.Fecha))
        ), 0) / 60.0, 2) AS Minutos_Activos
    FROM LogMotorFirma.Log l
    WHERE l.Fecha >= CURDATE()
      AND l.Documento IN ({placeholders})
    GROUP BY l.Documento
    ORDER BY Total_Errores_Tecnicos DESC, Minutos_Activos DESC;
    """
    
    try:
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                # AQUÍ SOLO EJECUTAMOS LA CONSULTA DE AUDITORÍA
                cur.execute(sql_auditoria, tuple(doc_list))
                resultados = cur.fetchall()

        # --------------------------------------------------------
        # 🟢 LÓGICA EN PYTHON PARA FILTRAR INACTIVOS A 3 MÁXIMO
        # --------------------------------------------------------
        inactivos = []
        otros = []
        
        # Separamos los casos inactivos de los casos reales con excepción
        for r in resultados:
            if r['Causa_Raiz'] == '👤 Inactividad del Cliente':
                inactivos.append(r)
            else:
                otros.append(r)
        
        total_inactivos = len(inactivos)
        
        # Inyectamos la columna 'Total_En_Categoria'
        for r in otros:
            r['Total_En_Categoria'] = len([x for x in otros if x['Causa_Raiz'] == r['Causa_Raiz']])
            
        for r in inactivos:
            r['Total_En_Categoria'] = total_inactivos
            
        # Unimos: Los errores reales + SOLO LOS PRIMEROS 3 inactivos
        resultados_finales = otros + inactivos[:3]
        
        return jsonify(resultados_finales)

    except Exception as e:
        return jsonify({"error": f"Error BD: {str(e)}"}), 500
    
    
    # ==========================================
# 📊 ENDPOINT EMBUDO FIRMA DIGITAL
# ==========================================
@app.route("/embudo-firma", methods=["GET"])
def embudo_firma():
    sql = """
    SELECT
        Etapa_Negocio,
        COUNT(DISTINCT IdProceso)   AS Total_Flujos,
        SUM(Errores_Por_Doc)        AS Errores_Tecnicos,
        ROUND(AVG(Minutos_Transcurridos), 2) AS Tiempo_Promedio_Min
    FROM (
        SELECT
            l.Documento AS IdProceso,
            CASE
                WHEN l.Metodo = 'SavePendingSignature'
                    THEN '1. Agil registra solicitud'
                WHEN l.Metodo IN ('GetDocumentsByProduct','GetClientBiometricData',
                     'GetInfoFromAgil','GetInformationFromAgil','GetArgumentsFromPDF',
                     'GetArgumentsByTemplate','GetArgumentsAsync','FillDocumentsAsync',
                     'ProcessTemplatePdfAsync','GetInfoToPdf','NonNegotiablesDocsAsync',
                     'DetermineListAndAddSoloFields','ExecuteBiometricsSP',
                     'ExecuteSpBiometrics','GetDecevalInfoFromAgil')
                  OR l.Descripcion LIKE '%GetDataClient%'
                  OR l.Descripcion LIKE '%APIAgilSOA%'
                    THEN '2. App consulta documentos'
                WHEN l.Descripcion LIKE '%Inicia proceso de Firma%'
                  OR l.Metodo IN ('ValidateBiometricProcess','ProcessBioResult',
                     'GetBiometricsResult','Initializate','CreateSingDetail')
                  OR l.Descripcion LIKE '%BiometricState%'
                  OR l.Descripcion LIKE '%Biometria%'
                    THEN '3. Biometria y firma inicial'
                WHEN l.Metodo IN ('WsSingSingProcess','SingPdfWsSingAsync',
                     'MapWsSingRequestAsync','RetrySingInWsSing',
                     'MapRetryWsSingRequest','RetrySingPdfWsSing')
                  OR l.Descripcion LIKE '%WsSing%'
                    THEN '4. Firma digital WsSing'
                WHEN l.Metodo IN ('ExecuteDecevalSP','CreatePayNoteAsync',
                     'GeneratePayNote','GetPayNoteAsync','DecevalSingProcess',
                     'SingPdfDecevalAsync','SingDocumentDecevalAsync',
                     'NegotiableDocsAsync','HandleNewlyCreated')
                  OR l.Descripcion LIKE '%Deceval%'
                  OR l.Descripcion LIKE '%pagare%'
                    THEN '5. Firma pagare Deceval'
                WHEN l.Metodo IN ('SavePdfAsync','GetSignedFiles','SendStateToAgil',
                     'HandleReportingProcess','SendFinalState','HandleResponse',
                     'ReportOriginator','SendMailAsync','SendMail')
                  OR l.Descripcion LIKE '%Nuevo estado de la solicitud: 1000%'
                  OR l.Descripcion LIKE '%envio de correo%'
                    THEN '6. Almacenamiento y reporte'
                ELSE NULL
            END AS Etapa_Negocio,
            MAX(CASE
                WHEN CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs)
                     LIKE '%Timeout%'
                  OR CONCAT_WS(' ', l.Descripcion, l.Adicional, l.Rs)
                     LIKE '%Exception%'
                THEN 1 ELSE 0
            END) AS Errores_Por_Doc,
            ROUND(TIMESTAMPDIFF(SECOND, MIN(l.Fecha), MAX(l.Fecha)) / 60.0, 2)
                AS Minutos_Transcurridos
        FROM LogMotorFirma.Log l
        WHERE DATE(l.Fecha) = CURDATE()
        GROUP BY l.Documento, Etapa_Negocio
    ) sub
    WHERE Etapa_Negocio IS NOT NULL
    GROUP BY Etapa_Negocio
    ORDER BY Etapa_Negocio
    """
    try:
        conn = get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

        # Calcular embudo acumulativo
        orden = ['1.','2.','3.','4.','5.','6.']
        mapa = {r['Etapa_Negocio']: r for r in rows}

        resultado = []
        acum = 0
        for prefijo in reversed(orden):
            key = next((k for k in mapa if k.startswith(prefijo)), None)
            acum += mapa[key]['Total_Flujos'] if key else 0

        total_entrada = acum
        acum = 0
        for prefijo in reversed(orden):
            key = next((k for k in mapa if k.startswith(prefijo)), None)
            acum += mapa[key]['Total_Flujos'] if key else 0
            resultado.insert(0, {
                'etapa': key or prefijo + ' (sin datos)',
                'count': acum,
                'total': total_entrada or 1,
                'pct': round((acum / (total_entrada or 1)) * 100, 1),
                'errores': mapa[key]['Errores_Tecnicos'] if key else 0,
                'tiempo_avg': mapa[key]['Tiempo_Promedio_Min'] if key else 0,
            })

        completados = resultado[-1]['count'] if resultado else 0
        return jsonify({
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'total_entrada': total_entrada,
            'total_completados': completados,
            'tasa_exito': round((completados / (total_entrada or 1)) * 100, 1),
            'etapas': resultado
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
    # (AQUÍ ARRIBA ESTÁN TUS ENDPOINTS, COMO @app.route("/auditoria-cruzada"))
@app.route("/health", methods=["GET"])
def health():
    try:
        conn = get_connection()
        conn.close()
        return jsonify({"status": "ok", "db": "conectado", "puerto": 5005})
    except Exception as e:
        return jsonify({"status": "error", "db": str(e)}), 500
    
if __name__ == "__main__":
    print("✅ Intentando iniciar MariaDB API en http://0.0.0.0:5005 ...")
    try:
        # Ejecutamos Flask directamente en el hilo principal
        app.run(host="0.0.0.0", port=5005, debug=False, use_reloader=False)
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {e}")
        input("Presiona ENTER para salir...") # Esto evita que la ventana del .exe se cierre de golpe