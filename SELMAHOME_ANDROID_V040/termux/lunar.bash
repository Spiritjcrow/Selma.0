[[ $- == *i* ]] || return
printf '\033[38;5;83m  ▄████▄    \033[38;5;177m▄██▄\n\033[38;5;83m  █ ▪▪ █    \033[38;5;177m█▪▪█\n\033[38;5;83m  ▀█▀▀█▀    \033[38;5;177m▀█▀█   \033[38;5;87mLUNAR RELAY\033[0m\n'
PS1='\[\e[38;5;83m\]moon\[\e[38;5;177m\]::\[\e[38;5;87m\]\w\[\e[0m\] \$ '
selma-afterhours() { printf '%s\n' 'D.P. and Skeeter · dealership shuttle on approach.'; }
