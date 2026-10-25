from flask import jsonify


class AppError(Exception):
    """Base class for application errors that should return a clean JSON response."""
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload


class InvalidInputError(AppError):
    status_code = 400


class ModelNotLoadedError(AppError):
    status_code = 503


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(err):
        response = {"success": False, "error": err.message}
        if err.payload:
            response["details"] = err.payload
        return jsonify(response), err.status_code

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"success": False, "error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"success": False, "error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def server_error(_e):
        app.logger.exception("Unhandled server error")
        return jsonify({"success": False, "error": "Internal server error"}), 500
