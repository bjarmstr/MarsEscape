                var source = new EventSource('/stream');
                var out = document.getElementById('out');
                source.onmessage = function(e) {
                    // XSS is prevented by using textContent instead of innerHTML
                    out.textContent= e.data;
                };
  
