const workTime = document.getElementById('Worktime')
const breakTime = document.getElementById('Breaktime')
const cycles = document.getElementById('Cycles')
const timer = document.getElementById('timer')
const phaseTracker = document.getElementById('phase')
const startButton = document.getElementById('startButton')
let countdownInterval
let isWorking = true
let remainingCycles = 0
let workSeconds=0
let breakSeconds=0
let currentTimeLeft = 0



function startPomodoro(){
    const workMins = parseInt(workTime.value)
    const breakMins = parseInt(breakTime.value)
    const totalCycles = parseInt(cycles.value)
    phaseTracker.innerHTML = 'Get to Work.'
    startButton.innerHTML = 'Reset'

    workSeconds = workMins*60
    breakSeconds = breakMins*60
    remainingCycles = totalCycles
    isWorking=true

    console.log(workSeconds,breakSeconds,totalCycles)
    startCountdown(workSeconds);
}

function startCountdown(initialTime){

    clearInterval(countdownInterval)
    
    let timeSeconds = initialTime;
    countdownInterval = setInterval(()=>{const min = Math.floor(timeSeconds/60)
    let seconds = timeSeconds % 60

    if (seconds<10) seconds = '0' + seconds

    timer.innerHTML = `${min}:${seconds}`

    if (timeSeconds<=0){
        clearInterval(countdownInterval)
        handlePeriodEnd()
        return
    }

    currentTimeLeft = timeSeconds

    timeSeconds--
},1000)
    
}

function handlePeriodEnd(){
    if (isWorking){
        isWorking = false
        startCountdown(breakSeconds)
        phaseTracker.innerHTML='Take a Break.'
    } else{
        remainingCycles--
        if (remainingCycles>0){
            isWorking=true
            startCountdown(workSeconds)
            phaseTracker.innerHTML = 'Get to Work.'
        } else{
            timer.innerHTML = 'Pomodoro Complete!'
            logSession()
            phaseTracker.innerHTML = 'Nice Job.'
            startButton.innerHTML = 'Start'
        }
    }
}

function pausePomodoro(){
    clearInterval(countdownInterval)

}

function resumePomodoro(){
    startCountdown(currentTimeLeft)
}

function logSession() {
    const data = {
        worktime: workSeconds / 60,
        breaktime: breakSeconds / 60,
        cycles: parseInt(cycles.value)
    };

    fetch('/log_session', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (response.ok) {
            console.log("Session logged successfully!");
            location.reload();
        } else {
            console.error("Failed to log session.");
        }
    })
    .catch(error => {
        console.error("Error logging session:", error);
    });
}