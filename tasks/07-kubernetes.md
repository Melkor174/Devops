# Этап 7. Kubernetes (k3s)

**Легенда.** Проект вырос, нужны самовосстановление, обновления без простоя и масштабирование. Переносим стенд в Kubernetes.

**Цель:** то же приложение работает в кластере; вы умеете его обновлять, откатывать и диагностировать.

Используйте **k3s**: облегчённый Kubernetes, ставится одной командой на ваш сервер. Для начала достаточно одной ноды (она будет и control plane, и worker). Установите `kubectl` и настройте kubeconfig. Для безопасных экспериментов можно локально использовать `kind` или `minikube`.

## Сначала словарь (запишите своими словами в NOTES.md)
Node, Pod, Deployment, ReplicaSet, Service, Ingress, ConfigMap, Secret, Namespace, PersistentVolumeClaim, StatefulSet, Probe (liveness/readiness), requests/limits.

## Задания

### 7.1 Кластер
- Установите k3s на сервер. Проверьте `kubectl get nodes` и `kubectl get pods -A`.
- Найдите, какие системные поды работают в `kube-system` и за что каждый отвечает.

### 7.2 Манифесты проекта
Создайте каталог `k8s/` и опишите в YAML (в отдельном namespace `notes`):
- **Postgres:** StatefulSet (или Deployment) + PersistentVolumeClaim + Service. Пароль в **Secret**.
- **Redis:** Deployment + Service.
- **App:** Deployment на 2 реплики, образ из вашего ghcr, настройки из ConfigMap/Secret, **readinessProbe и livenessProbe** на `/health`, `resources.requests/limits`.
- **Ingress:** внешний доступ к приложению по HTTP (k3s приходит с Traefik).
- Применение: `kubectl apply -f k8s/`.

### 7.3 Эксперименты
1. Удалите под `app` (`kubectl delete pod …`). Что делает Deployment?
2. Масштабируйте до 4 реплик (`kubectl scale`), затем обратно. Как трафик распределяется между подами?
3. **Rolling update:** выкатите новую версию образа. Следите за `kubectl rollout status`. Затем выкатите заведомо сломанный образ: что происходит со старыми подами? Откат: `kubectl rollout undo`.
4. Удалите под Postgres: данные на месте? Почему (PVC)?
5. Остановите Postgres (`kubectl scale … --replicas=0`). Что с readiness приложения? Получает ли Service трафик на «неготовые» поды?

### 7.4 Диагностика (главный навык)
Устройте и найдите причину каждого статуса:
| Статус | Как вызвать | Где смотреть |
|---|---|---|
| `ImagePullBackOff` | неверное имя/тег образа | `kubectl describe pod` → Events |
| `CrashLoopBackOff` | неверный пароль БД | `kubectl logs <pod>` и `--previous` |
| `OOMKilled` | лимит памяти 100Mi + `/chaos/leak` | `kubectl describe pod` → Last State |
| `Pending` | requests больше, чем есть на ноде | `kubectl describe pod` → Events |
| Service без ответа | неверный label в selector | `kubectl get endpoints`, `kubectl describe svc` |

Алгоритм для каждого: `kubectl get pods` → `describe` → `logs` → `get events --sort-by=.lastTimestamp`.

### 7.5 Мониторинг в кластере (по желанию)
- Установите Prometheus + Grafana через **Helm** (chart `kube-prometheus-stack`).
- Добавьте сбор метрик приложения (ServiceMonitor или аннотации/доп. scrape).
- Найдите на дашбордах CPU/память подов и перезапуски (restarts).

### 7.6 Разница с Docker (письменно)
Что в Kubernetes делает то, что в compose делали вы руками: перезапуск, healthcheck, обновление, масштабирование, секреты, сеть? Чего compose не умеет?

## Готово, если
- [ ] Приложение доступно по HTTP через Ingress, база сохраняет данные при пересоздании пода.
- [ ] Вы выкатили новую версию без простоя и откатили плохую.
- [ ] Вы без подсказок диагностируете `CrashLoopBackOff`, `ImagePullBackOff`, `OOMKilled`, `Pending`.
- [ ] Вы объясняете разницу между Docker и Kubernetes, и что такое node/pod/worker, без шпаргалки.

## Подсказки
- Шпаргалка: `kubectl get/describe/logs/exec/apply/delete/rollout/scale/top`.
- Удобно: `kubectl config set-context --current --namespace=notes`, алиас `k=kubectl`, `k9s` как TUI.
- Поды видят сервисы по DNS-имени (`db.notes.svc`), так же как контейнеры в compose по имени сервиса.
- Не храните пароли в ConfigMap и в Git в открытом виде.

## Что дальше
Helm-чарт для проекта, GitOps (ArgoCD), HPA (автоскейлинг), сетевые политики, облачный Kubernetes.
