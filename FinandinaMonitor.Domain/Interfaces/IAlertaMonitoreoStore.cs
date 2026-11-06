using System;
using System.Collections.Generic;
using FinandinaMonitor.Domain.Entities;

namespace FinandinaMonitor.Domain.Interfaces
{
    public interface IAlertaMonitoreoStore
    {
        AlertaMonitoreo Crear(AlertaMonitoreo alerta);

        IReadOnlyList<AlertaMonitoreo> ObtenerActivas();

        IReadOnlyList<AlertaMonitoreo> ObtenerTodas();

        void ActualizarEvaluacion(Guid id, int conteo, bool disparada);

        void Desactivar(Guid id);

        /// <summary>
        /// Edita los criterios de una alerta activa (código de firma/biometría, término, umbral y duración).
        /// La fecha de expiración se recalcula a partir de la fecha de creación original y la nueva duración.
        /// Devuelve la alerta actualizada, o null si no existe o ya no está activa.
        /// </summary>
        AlertaMonitoreo? Editar(Guid id, string descripcion, int? estadoFirma, int? estadoBiometria, string? termino, int umbral, int duracionMinutos);

        /// <summary>
        /// Desactiva las alertas cuya ventana de tiempo ya expiró.
        /// Devuelve la cantidad de alertas expiradas.
        /// </summary>
        int DesactivarVencidas();
    }
}
