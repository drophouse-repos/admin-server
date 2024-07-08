async def format_error(path, name, code, exception):
	if not exception :
		exception = {}

	if(isinstance(exception, str)):
		_exception = {
			"detail" : exception 
		}
		exception = _exception

	exe = {
		"Status Code": code if code else 500,
		"File Name": exception["currentFrame"].filename.split('/')[-1] if "currentFrame" in exception else 'Not-Found',
		"Router Path": path if path else "Path Not-Found",
		"API Name": name if name else "Name Not-Found",
		"Exc. Raised Line_no": exception["currentFrame"].lineno if "currentFrame" in exception else 'Not-Found',
		"ERROR": f"HTTP Exception Handler: {code if code else 500}",
		"ERROR MESSAGE": exception["message"] if "message" in exception else 'Message Not-Found',
		"ERROR DETAILS": exception["detail"] if "detail" in exception else 'Detail Not-Found'	
	}

	return exe