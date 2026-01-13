/* beauty.js — Global JS for Lumière Beauty Recommendation System */

document.addEventListener('DOMContentLoaded', () => {

  // ----------------------------------------------------------------
  // Auto-dismiss flash messages after 5 seconds
  // ----------------------------------------------------------------
  document.querySelectorAll('.alert-beauty').forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease';
      alert.style.opacity    = '0';
      setTimeout(() => alert.remove(), 500);
    }, 5000);
  });

  // ----------------------------------------------------------------
  // Smooth scroll for same-page anchor links (admin sidebar)
  // ----------------------------------------------------------------
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', e => {
      const target = document.querySelector(link.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Update active class on admin sidebar links
        document.querySelectorAll('.admin-nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
      }
    });
  });

  // ----------------------------------------------------------------
  // Admin sidebar: highlight nav item on scroll
  // ----------------------------------------------------------------
  const adminSections = document.querySelectorAll('section[id]');
  if (adminSections.length) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          document.querySelectorAll('.admin-nav-link').forEach(l => l.classList.remove('active'));
          const link = document.querySelector(`.admin-nav-link[href="#${entry.target.id}"]`);
          if (link) link.classList.add('active');
        }
      });
    }, { threshold: 0.4 });
    adminSections.forEach(s => observer.observe(s));
  }

  // ----------------------------------------------------------------
  // Navbar mobile hamburger fix (ensure only one menu div)
  // ----------------------------------------------------------------
  const hamburger = document.querySelector('[onclick*="navMenu"]');
  if (hamburger) {
    hamburger.addEventListener('click', () => {
      const menus = document.querySelectorAll('#navMenu');
      // Toggle the last one (mobile menu)
      const mobile = menus[menus.length - 1];
      mobile.classList.toggle('d-none');
    });
  }

});
