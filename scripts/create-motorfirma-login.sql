-- Ejecutar conectado a la instancia 192.168.118.53,61733 con un usuario que tenga permisos de administración.
-- Crea un login SQL Server dedicado, de solo lectura, para que el contenedor Docker se conecte a MotorFirma
-- sin depender de autenticación integrada de Windows (que no existe dentro de un contenedor Linux).

USE [master];
GO

CREATE LOGIN [n8n_finandina_monitor] WITH PASSWORD = N'CambiaEstaClave123!', CHECK_POLICY = ON;
GO

USE [MotorFirma];
GO

CREATE USER [n8n_finandina_monitor] FOR LOGIN [n8n_finandina_monitor];
GO

-- Solo lectura sobre el esquema PendienteFirma (Estados, Solicitudes), que es lo único que consulta la app.
ALTER ROLE [db_datareader] ADD MEMBER [n8n_finandina_monitor];
GO
