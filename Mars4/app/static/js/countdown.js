var downloadTimer = setInterval(function(){
  if(countdown <= 0){
    clearInterval(downloadTimer);
    document.getElementById("countdown").innerHTML = "NONE: GAME OVER";
  } else {
  	let minutesleft = Math.floor(countdown/60);
  	let secondsleft = Math.floor(countdown-(minutesleft*60));
    document.getElementById("countdown").innerHTML = minutesleft + " minutes " + secondsleft + " seconds";

    
  }
  countdown -= 1;
  console.log(countdown, "seconds left");
}, 1000);