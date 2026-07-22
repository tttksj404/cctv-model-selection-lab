export function NotificationDropdown({ notifications }) {
  return (
    <section className="notification-panel">
      <div className="panel-title">알림</div>
      {notifications.map((item) => {
        const Icon = item.icon;
        return (
          <div className={`notification-item ${item.unread ? "unread" : ""}`} key={item.id}>
            <Icon size={16} />
            <div>
              <strong>{item.title}</strong>
              <p>{item.message}</p>
            </div>
          </div>
        );
      })}
    </section>
  );
}
