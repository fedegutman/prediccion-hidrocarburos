# ADR-NNN: Canal de notificaciones: Slack

**Fecha**: 2026-04-15
**Estado**: Aceptado

## Contexto

La Adenda Técnica Fase 1 requiere alertas automáticas que notifiquen al equipo ante incumplimiento de KPIs. La adenda menciona explícitamente como opciones: email o Slack. Se debe elegir un canal de notificación que el equipo pueda monitorear de forma práctica durante el desarrollo y la operación del servicio.

## Alternativas consideradas

- **Email**: No requiere infraestructura adicional pero implica configurar un servidor SMTP o usar un servicio externo. Las notificaciones por email tienden a perderse entre otros correos y en operación, el email genera ruido y las alertas compiten con otros correos, reduciendo la probabilidad de respuesta rápida.

- **Slack**: Permite crear un workspace gratuito con canales dedicados a alertas. La integración se realiza mediante Incoming Webhooks, que generan una URL única a la que Alertmanager hace un POST para enviar el mensaje. No requiere infraestructura adicional ni configuración de SMTP.

## Decisión

Se utiliza Slack con un canal dedicado a alertas operativas. Alertmanager envía notificaciones mediante un Incoming Webhook configurado en el workspace del equipo. La URL del webhook se almacena fuera del repositorio (`.gitignore`) para evitar exponer el secreto.

## Consecuencias

**Pros:**
- Canal de comunicación ya usado por equipos durante desarrollos
- Notificaciones en tiempo real con visibilidad inmediata
- Configuración simple: una URL de webhook, sin SMTP ni infraestructura extra
- Mensajes con formato enriquecido (título, descripción, severidad)
- Notificaciones de resolución además de disparo

**Contras:**
- Requiere que todos los miembros del equipo tengan acceso al workspace de Slack
- La URL del webhook es un secreto que debe gestionarse fuera del repositorio
