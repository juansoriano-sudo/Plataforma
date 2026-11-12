namespace FinandinaMonitor.Domain.Interfaces
{
    /// <summary>
    /// Lock global (toda la app, todas las sesiones) para que solo se ejecute un lote de
    /// reproceso a la vez, aunque haya varios usuarios conectados al mismo tiempo.
    /// </summary>
    public interface IReprocesoLockService
    {
        /// <summary>
        /// Intenta tomar el lock para <paramref name="usuario"/>. Si ya está ocupado,
        /// devuelve false y <paramref name="usuarioEnCurso"/> indica quién lo tiene.
        /// </summary>
        bool TryAcquire(string? usuario, out string? usuarioEnCurso);

        void Release();
    }
}
