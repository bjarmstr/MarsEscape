                var source = new EventSource('/stream');
                          	
                source.onmessage = function(e) {
                	
					let jsonstr = e.data;
					console.log(jsonstr,"stream name and time id were not passed along");
					console.log(typeof jsonstr,"not a dictionary?")
					const jj = JSON.parse(jsonstr)
					console.log(typeof jj,"object please", jj)
					for (var keyname in jj){
						console.log(keyname, jj[keyname],"key,value")
						let idname = document.getElementById(keyname);
						let idvalue =jj[keyname];
					console.log(idname,"name")
               		// XSS is prevented by using textContent instead of innerHTML
                    idname.textContent= parseInt(idvalue);
					};
					
                };
  
