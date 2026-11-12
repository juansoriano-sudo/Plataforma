using System.Threading;
using FinandinaMonitor.Domain.Interfaces;

namespace FinandinaMonitor.Application.Services
{
    public class ReprocesoLockService : IReprocesoLockService
    {
        private readonly SemaphoreSlim _semaforo = new(1, 1);
        private string? _usuarioEnCurso;

        public bool TryAcquire(string? usuario, out string? usuarioEnCurso)
        {
            if (!_semaforo.Wait(0))
            {
                usuarioEnCurso = _usuarioEnCurso;
                return false;
            }

            _usuarioEnCurso = usuario;
            usuarioEnCurso = null;
            return true;
        }

        public void Release()
        {
            _usuarioEnCurso = null;
            _semaforo.Release();
        }
    }
}
